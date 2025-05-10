"""
Topic Management Service

This service manages Kafka topics, ensuring they exist with appropriate configurations.
"""

import os
import logging
import asyncio
from typing import Dict, List, Any, Optional
from aiokafka.admin import AIOKafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError, KafkaError

logger = logging.getLogger(__name__)

# Define standard topics used in the RAG microservices
DEFAULT_TOPICS = {
    "document_events": {
        "partitions": 3,
        "replication_factor": 1,
        "configs": {
            "retention.ms": str(7 * 24 * 60 * 60 * 1000),  # 7 days retention
            "cleanup.policy": "delete"
        }
    },
    "metadata_enrichment": {
        "partitions": 3,
        "replication_factor": 1,
        "configs": {
            "retention.ms": str(7 * 24 * 60 * 60 * 1000),  # 7 days retention
            "cleanup.policy": "delete"
        }
    },
    "query_events": {
        "partitions": 3,
        "replication_factor": 1,
        "configs": {
            "retention.ms": str(3 * 24 * 60 * 60 * 1000),  # 3 days retention
            "cleanup.policy": "delete"
        }
    },
    "llm_tasks": {
        "partitions": 3,
        "replication_factor": 1,
        "configs": {
            "retention.ms": str(2 * 24 * 60 * 60 * 1000),  # 2 days retention
            "cleanup.policy": "delete"
        }
    },
    "system_events": {
        "partitions": 2,
        "replication_factor": 1,
        "configs": {
            "retention.ms": str(14 * 24 * 60 * 60 * 1000),  # 14 days retention
            "cleanup.policy": "delete"
        }
    }
}


class TopicManagementService:
    """
    Service for managing Kafka topics.
    """
    
    def __init__(self, bootstrap_servers: str, topics: Optional[Dict[str, Dict[str, Any]]] = None):
        """
        Initialize the topic management service.
        
        Args:
            bootstrap_servers: Kafka bootstrap servers, comma-separated
            topics: Optional dictionary of topics to manage, with configuration
        """
        self.bootstrap_servers = bootstrap_servers
        self.topics = topics if topics is not None else DEFAULT_TOPICS
        self.admin_client = None
    
    async def _get_admin_client(self) -> AIOKafkaAdminClient:
        """
        Get or create an admin client.
        
        Returns:
            An initialized AIOKafkaAdminClient
        """
        if self.admin_client is None:
            self.admin_client = AIOKafkaAdminClient(
                bootstrap_servers=self.bootstrap_servers,
                client_id="kafka-utility-topic-manager"
            )
            await self.admin_client.start()
        return self.admin_client
    
    async def ensure_topic_exists(self, topic_name: str, partitions: int = 1, 
                                  replication_factor: int = 1, configs: Dict[str, str] = None) -> bool:
        """
        Ensure that a topic exists, creating it if necessary.
        
        Args:
            topic_name: Name of the topic
            partitions: Number of partitions
            replication_factor: Replication factor
            configs: Topic configuration
            
        Returns:
            True if the topic exists or was created, False on error
        """
        try:
            admin_client = await self._get_admin_client()
            
            # Check if the topic already exists
            existing_topics = await admin_client.list_topics()
            if topic_name in existing_topics:
                logger.info(f"Topic '{topic_name}' already exists")
                return True
            
            # Create the topic
            new_topic = NewTopic(
                name=topic_name,
                num_partitions=partitions,
                replication_factor=replication_factor,
                topic_configs=configs or {}
            )
            
            await admin_client.create_topics([new_topic])
            logger.info(f"Created topic '{topic_name}' with {partitions} partitions")
            return True
            
        except TopicAlreadyExistsError:
            # This can happen in race conditions, it's not an error
            logger.info(f"Topic '{topic_name}' already exists (concurrently created)")
            return True
            
        except Exception as e:
            logger.error(f"Error ensuring topic '{topic_name}' exists: {e}")
            return False
    
    async def ensure_required_topics(self) -> bool:
        """
        Ensure all required topics exist, creating any that don't.
        
        Returns:
            True if all topics exist or were created, False if any failed
        """
        try:
            # Create each topic in parallel
            tasks = []
            for topic_name, config in self.topics.items():
                task = asyncio.create_task(
                    self.ensure_topic_exists(
                        topic_name=topic_name,
                        partitions=config.get("partitions", 1),
                        replication_factor=config.get("replication_factor", 1),
                        configs=config.get("configs", {})
                    )
                )
                tasks.append(task)
            
            # Wait for all tasks to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Check for any failed topics
            success = True
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Error creating topic: {result}")
                    success = False
                elif not result:
                    success = False
            
            return success
            
        except Exception as e:
            logger.error(f"Error ensuring required topics: {e}")
            return False
    
    async def delete_topic(self, topic_name: str) -> bool:
        """
        Delete a topic.
        
        Args:
            topic_name: Name of the topic to delete
            
        Returns:
            True if the topic was deleted, False otherwise
        """
        try:
            admin_client = await self._get_admin_client()
            await admin_client.delete_topics([topic_name])
            logger.info(f"Deleted topic '{topic_name}'")
            return True
        except Exception as e:
            logger.error(f"Error deleting topic '{topic_name}': {e}")
            return False
    
    async def list_topics(self) -> List[str]:
        """
        List all topics.
        
        Returns:
            List of topic names
        """
        try:
            admin_client = await self._get_admin_client()
            topics = await admin_client.list_topics()
            return topics
        except Exception as e:
            logger.error(f"Error listing topics: {e}")
            return []
    
    async def close(self):
        """Close the admin client."""
        if self.admin_client:
            try:
                await self.admin_client.close()
                self.admin_client = None
            except Exception as e:
                logger.error(f"Error closing admin client: {e}")


if __name__ == "__main__":
    # Simple test for the topic management service
    async def test_topics():
        logging.basicConfig(level=logging.INFO)
        bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        
        topic_service = TopicManagementService(bootstrap_servers=bootstrap_servers)
        
        # List existing topics
        topics = await topic_service.list_topics()
        print(f"Existing topics: {topics}")
        
        # Ensure required topics exist
        success = await topic_service.ensure_required_topics()
        print(f"Created required topics: {success}")
        
        # List topics again to verify
        topics = await topic_service.list_topics()
        print(f"Topics after creation: {topics}")
        
        await topic_service.close()
    
    asyncio.run(test_topics())
