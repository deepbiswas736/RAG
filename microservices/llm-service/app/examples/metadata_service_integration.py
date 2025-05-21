"""
Metadata Service Integration Example

This module shows how to integrate the refactored metadata consumer services.
"""

import os
import asyncio
import logging
from typing import Dict, Any

from ..infrastructure.factories.metadata_service_factory import MetadataServiceFactory
from ..application.services.llm_service import LLMService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def create_and_start_metadata_consumer_service():
    """
    Create and start the metadata consumer service with all dependencies
    
    Returns:
        Running metadata consumer service
    """
    # Configuration for Kafka consumer
    consumer_config = {
        "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"),
        "group.id": os.getenv("KAFKA_CONSUMER_GROUP_ID", "llm-service-metadata-group"),
        "auto.offset.reset": "earliest"
    }
    
    # Configuration for Kafka producer
    producer_config = {
        "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    }
    
    # Document topic
    document_topic = os.getenv("DOCUMENT_METADATA_TOPIC", "document-metadata")
    
    # Create LLM service
    llm_service = LLMService()
    await llm_service.initialize()
    
    # Create metadata consumer service
    metadata_service = await MetadataServiceFactory.create_metadata_consumer_service(
        consumer_config=consumer_config,
        document_topic=document_topic,
        producer_config=producer_config,
        llm_service=llm_service
    )
    
    # Start consuming messages
    await metadata_service.start()
    
    return metadata_service

async def main():
    """Main entry point for the service"""
    
    logger.info("Starting Metadata Consumer Service")
    
    try:
        # Create and start metadata consumer service
        service = await create_and_start_metadata_consumer_service()
        
        # Run indefinitely
        while True:
            await asyncio.sleep(60)
            
    except KeyboardInterrupt:
        logger.info("Shutting down Metadata Consumer Service")
    except Exception as e:
        logger.error(f"Error running Metadata Consumer Service: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())
