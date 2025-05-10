#!/usr/bin/env python
"""
Kafka Utility Service for the RAG microservices architecture.
This service provides standardized Kafka messaging patterns and client libraries.
"""

import os
import sys
import logging
import asyncio
from dotenv import load_dotenv

# Setup path to load modules from app directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.application.services.schema_registry_service import SchemaRegistryService
from app.application.services.kafka_health_service import KafkaHealthService
from app.application.services.topic_management_service import TopicManagementService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("kafka_utility")

# Load environment variables from .env file
load_dotenv()

# Kafka broker configuration
BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
SECURITY_PROTOCOL = os.getenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT")
AUTO_CREATE_TOPICS = os.getenv("KAFKA_AUTO_CREATE_TOPICS", "True").lower() == "true"


async def init_services():
    """Initialize services and perform startup tasks."""
    try:
        logger.info(f"Initializing Kafka Utility Service with brokers: {BOOTSTRAP_SERVERS}")
        
        # Initialize schema registry service
        schema_registry = SchemaRegistryService()
        await schema_registry.initialize()
        logger.info("Schema registry initialized")
        
        # Initialize health service to check connection to Kafka
        health_service = KafkaHealthService(bootstrap_servers=BOOTSTRAP_SERVERS)
        kafka_available = await health_service.check_kafka_availability()
        if not kafka_available:
            logger.error("Kafka is not available")
            return False
        logger.info("Kafka health check completed successfully")
        
        # Initialize topic management service
        topic_mgmt = TopicManagementService(bootstrap_servers=BOOTSTRAP_SERVERS)
        if AUTO_CREATE_TOPICS:
            await topic_mgmt.ensure_required_topics()
            logger.info("Required topics created or verified")
        
        return True
        
    except Exception as e:
        logger.error(f"Error initializing services: {e}")
        return False


async def health_check():
    """Continuous health check for Kafka connectivity."""
    health_service = KafkaHealthService(bootstrap_servers=BOOTSTRAP_SERVERS)
    while True:
        try:
            await health_service.check_kafka_availability()
            await asyncio.sleep(30)  # Check every 30 seconds
        except Exception as e:
            logger.error(f"Health check error: {e}")
            await asyncio.sleep(5)  # Shorter retry interval on error


async def main():
    """Main entry point for the service."""
    success = await init_services()
    if not success:
        logger.error("Failed to initialize services, exiting")
        return 1
    
    # Start health check background task
    health_check_task = asyncio.create_task(health_check())
    
    try:
        # Keep the service running
        logger.info("Kafka Utility Service is running")
        while True:
            await asyncio.sleep(3600)  # Sleep for an hour
    except asyncio.CancelledError:
        logger.info("Service shutdown initiated")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1
    finally:
        # Cancel background tasks
        health_check_task.cancel()
        try:
            await health_check_task
        except asyncio.CancelledError:
            pass
        
        logger.info("Kafka Utility Service shutdown complete")
    
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        logger.info("Service terminated by user")
        sys.exit(0)
