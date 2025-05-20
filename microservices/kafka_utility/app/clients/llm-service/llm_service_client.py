"""
LLM Service Kafka Client

This module provides a client for interacting with the LLM Service via Kafka.
"""

import os
import logging
import uuid
from typing import Dict, Any, List, Optional, Union

from ...application.services.schema_registry_service import SchemaRegistryService
from ...infrastructure.adapters.kafka_producer import KafkaProducerAdapter
from ...infrastructure.utils.message_serialization import MessageSerializer

logger = logging.getLogger(__name__)

class LLMServiceKafkaClient:
    """
    Client for interacting with the LLM Service via Kafka.
    """
    
    def __init__(self, bootstrap_servers: Optional[str] = None):
        """
        Initialize the LLM Service Kafka client.
        
        Args:
            bootstrap_servers: Optional Kafka bootstrap servers.
                               If None, uses KAFKA_BOOTSTRAP_SERVERS environment variable.
        """
        self.bootstrap_servers = bootstrap_servers or os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        self.producer = KafkaProducerAdapter(bootstrap_servers=self.bootstrap_servers)
        
        # Initialize schema registry
        self.schema_registry = SchemaRegistryService()
        self.message_serializer = MessageSerializer(schema_registry=self.schema_registry)
        
    async def initialize(self) -> None:
        """Initialize the client."""
        await self.schema_registry.initialize()
    
    async def send_embedding_request(self, task_id: str, input_text: Union[str, List[str]], 
                                   model: str = "default",
                                   priority: int = 5) -> bool:
        """
        Send an embedding request event.
        
        Args:
            task_id: The ID of the embedding task
            input_text: The text to embed (string or list of strings)
            model: The embedding model to use
            priority: Task priority (0-10, higher is more important)
            
        Returns:
            True if the event was sent successfully, False otherwise
        """
        payload = {
            "taskId": task_id,
            "taskType": "embedding",
            "model": model,
            "priority": priority,
            "input": input_text
        }
        
        # Create message envelope
        correlation_id = str(uuid.uuid4())
        envelope = self.message_serializer.create_envelope(
            payload=payload,
            message_type="llm.embedding.request",
            metadata={"correlationId": correlation_id}
        )
        
        # Validate against schema
        if not self.message_serializer.validate_message(envelope, "llm_task"):
            logger.error(f"Invalid embedding request event for task {task_id}")
            return False
        
        # Send message
        return await self.producer.send_message(
            topic="llm_tasks",
            key=task_id,
            value=envelope
        )
    
    async def send_completion_request(self, task_id: str, input_text: str,
                                    model: str = "default",
                                    priority: int = 5,
                                    options: Optional[Dict[str, Any]] = None) -> bool:
        """
        Send a completion request event.
        
        Args:
            task_id: The ID of the completion task
            input_text: The prompt text
            model: The LLM model to use
            priority: Task priority (0-10, higher is more important)
            options: Optional model parameters (temperature, max_tokens, etc.)
            
        Returns:
            True if the event was sent successfully, False otherwise
        """
        payload = {
            "taskId": task_id,
            "taskType": "completion",
            "model": model,
            "priority": priority,
            "input": input_text
        }
        
        if options:
            payload["options"] = options
        
        # Create message envelope
        correlation_id = str(uuid.uuid4())
        envelope = self.message_serializer.create_envelope(
            payload=payload,
            message_type="llm.completion.request",
            metadata={"correlationId": correlation_id}
        )
        
        # Validate against schema
        if not self.message_serializer.validate_message(envelope, "llm_task"):
            logger.error(f"Invalid completion request event for task {task_id}")
            return False
        
        # Send message
        return await self.producer.send_message(
            topic="llm_tasks",
            key=task_id,
            value=envelope
        )
    
    async def send_embedding_response(self, task_id: str, embedding_results: List[List[float]],
                                    processing_time: float) -> bool:
        """
        Send an embedding response event.
        
        Args:
            task_id: The ID of the embedding task
            embedding_results: The embedding results (list of vector lists)
            processing_time: Processing time in seconds
            
        Returns:
            True if the event was sent successfully, False otherwise
        """
        payload = {
            "taskId": task_id,
            "taskType": "embedding",
            "embeddingResults": embedding_results,
            "processingTime": processing_time
        }
        
        # Create message envelope
        envelope = self.message_serializer.create_envelope(
            payload=payload,
            message_type="llm.embedding.response",
            metadata={"correlationId": str(uuid.uuid4())}
        )
        
        # Validate against schema
        if not self.message_serializer.validate_message(envelope, "llm_task"):
            logger.error(f"Invalid embedding response event for task {task_id}")
            return False
        
        # Send message
        return await self.producer.send_message(
            topic="llm_tasks",
            key=task_id,
            value=envelope
        )
    
    async def send_completion_response(self, task_id: str, completion_result: str,
                                     processing_time: float) -> bool:
        """
        Send a completion response event.
        
        Args:
            task_id: The ID of the completion task
            completion_result: The completion result text
            processing_time: Processing time in seconds
            
        Returns:
            True if the event was sent successfully, False otherwise
        """
        payload = {
            "taskId": task_id,
            "taskType": "completion",
            "completionResults": completion_result,
            "processingTime": processing_time
        }
        
        # Create message envelope
        envelope = self.message_serializer.create_envelope(
            payload=payload,
            message_type="llm.completion.response",
            metadata={"correlationId": str(uuid.uuid4())}
        )
        
        # Validate against schema
        if not self.message_serializer.validate_message(envelope, "llm_task"):
            logger.error(f"Invalid completion response event for task {task_id}")
            return False
        
        # Send message
        return await self.producer.send_message(
            topic="llm_tasks",
            key=task_id,
            value=envelope
        )
    
    async def send_task_failed_event(self, task_id: str, task_type: str,
                                   error_message: str, error_code: Optional[str] = None) -> bool:
        """
        Send a task failed event.
        
        Args:
            task_id: The ID of the task
            task_type: The type of task ("embedding" or "completion")
            error_message: The error message
            error_code: Optional error code
            
        Returns:
            True if the event was sent successfully, False otherwise
        """
        error = {
            "message": error_message
        }
        
        if error_code:
            error["code"] = error_code
            
        payload = {
            "taskId": task_id,
            "taskType": task_type,
            "error": error
        }
        
        # Create message envelope
        envelope = self.message_serializer.create_envelope(
            payload=payload,
            message_type="llm.task.failed",
            metadata={"correlationId": str(uuid.uuid4())}
        )
        
        # Validate against schema
        if not self.message_serializer.validate_message(envelope, "llm_task"):
            logger.error(f"Invalid task failed event for task {task_id}")
            return False
        
        # Send message
        return await self.producer.send_message(
            topic="llm_tasks",
            key=task_id,
            value=envelope
        )
    
    async def close(self) -> None:
        """Close the client."""
        await self.producer.close()
