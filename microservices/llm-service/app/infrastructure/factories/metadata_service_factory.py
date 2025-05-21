"""
Metadata Service Factory

Factory for creating instances of metadata service classes.
"""

import logging
from typing import Dict, Any, Optional

from kafka_utility.app.infrastructure.adapters.kafka_consumer import KafkaConsumerAdapter
from kafka_utility.app.infrastructure.adapters.kafka_producer import KafkaProducerAdapter
from kafka_utility.app.clients.document_service import DocumentServiceKafkaClient
from kafka_utility.app.clients.llm_service import LLMServiceKafkaClient
from ...application.services.llm_service import LLMService
from ..persistence.mongodb_client import MongoDBClient

from ...domain.services.document_retrieval_service import DocumentRetrievalService
from ...domain.services.document_summarizer import DocumentSummarizer
from ...domain.services.topic_extractor import TopicExtractor
from ...domain.services.metadata_updater import MetadataUpdater

from ..messaging.refactored_metadata_consumer import MetadataConsumerService

logger = logging.getLogger(__name__)

class MetadataServiceFactory:
    """Factory for creating metadata service instances"""
    
    @staticmethod
    async def create_metadata_consumer_service(
        consumer_config: Dict[str, Any],
        document_topic: str,
        producer_config: Dict[str, Any],
        llm_service: LLMService,
        max_concurrent_tasks: int = 5
    ) -> MetadataConsumerService:
        """
        Create and initialize a MetadataConsumerService with all required dependencies
        
        Args:
            consumer_config: Configuration for the Kafka consumer
            document_topic: The Kafka topic for document metadata
            producer_config: Configuration for the Kafka producer
            llm_service: Instance of LLMService
            max_concurrent_tasks: Maximum concurrent processing tasks
            
        Returns:
            Initialized MetadataConsumerService instance
        """
        # Create the service
        service = MetadataConsumerService(
            consumer_config=consumer_config,
            document_topic=document_topic,
            producer_config=producer_config,
            llm_service=llm_service,
            max_concurrent_tasks=max_concurrent_tasks
        )
        
        # Initialize service
        await service.initialize()
        
        return service
    
    @staticmethod
    async def create_document_retrieval_service(
        document_client: Optional[DocumentServiceKafkaClient] = None,
        mongo_client: Optional[MongoDBClient] = None,
        producer_adapter: Optional[KafkaProducerAdapter] = None,
        mongo_url: Optional[str] = None,
        db_name: Optional[str] = None
    ) -> DocumentRetrievalService:
        """
        Create a DocumentRetrievalService instance
        
        Args:
            document_client: Optional existing DocumentServiceKafkaClient
            mongo_client: Optional existing MongoDBClient
            producer_adapter: Optional KafkaProducerAdapter for creating a new document_client
            mongo_url: Optional MongoDB URL for creating a new mongo_client
            db_name: Optional database name for creating a new mongo_client
            
        Returns:
            DocumentRetrievalService instance
        """
        # Create clients if not provided
        if not document_client and producer_adapter:
            document_client = DocumentServiceKafkaClient(producer=producer_adapter)
            
        if not mongo_client:
            mongo_client = MongoDBClient(mongo_url, db_name)
            await mongo_client.initialize()
            
        # Create and return service
        return DocumentRetrievalService(document_client, mongo_client)
    
    @staticmethod
    def create_document_summarizer(llm_service: LLMService) -> DocumentSummarizer:
        """
        Create a DocumentSummarizer instance
        
        Args:
            llm_service: LLMService instance
            
        Returns:
            DocumentSummarizer instance
        """
        return DocumentSummarizer(llm_service)
    
    @staticmethod
    def create_topic_extractor(llm_service: LLMService) -> TopicExtractor:
        """
        Create a TopicExtractor instance
        
        Args:
            llm_service: LLMService instance
            
        Returns:
            TopicExtractor instance
        """
        return TopicExtractor(llm_service)
    
    @staticmethod
    async def create_metadata_updater(
        document_client: Optional[DocumentServiceKafkaClient] = None,
        mongo_client: Optional[MongoDBClient] = None,
        producer_adapter: Optional[KafkaProducerAdapter] = None,
        mongo_url: Optional[str] = None,
        db_name: Optional[str] = None
    ) -> MetadataUpdater:
        """
        Create a MetadataUpdater instance
        
        Args:
            document_client: Optional existing DocumentServiceKafkaClient
            mongo_client: Optional existing MongoDBClient
            producer_adapter: Optional KafkaProducerAdapter for creating a new document_client
            mongo_url: Optional MongoDB URL for creating a new mongo_client
            db_name: Optional database name for creating a new mongo_client
            
        Returns:
            MetadataUpdater instance
        """
        # Create clients if not provided
        if not document_client and producer_adapter:
            document_client = DocumentServiceKafkaClient(producer=producer_adapter)
            
        if not mongo_client:
            mongo_client = MongoDBClient(mongo_url, db_name)
            await mongo_client.initialize()
            
        # Create and return service
        return MetadataUpdater(document_client, mongo_client)
