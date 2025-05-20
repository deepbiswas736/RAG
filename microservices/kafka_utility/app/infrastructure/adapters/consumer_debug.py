"""
Debug helpers for Kafka consumer.
"""
import logging
import asyncio
from typing import Any

logger = logging.getLogger(__name__)

async def diagnose_kafka_connection(bootstrap_servers: str, topic: str):
    """
    Diagnose Kafka connection and topic issues.
    
    Args:
        bootstrap_servers: Kafka bootstrap servers
        topic: Topic to check
    """
    logger.info(f"Diagnosing Kafka connection to {bootstrap_servers} for topic {topic}")
    
    try:
        # Import here to avoid circular dependency
        from kafka import KafkaConsumer, KafkaProducer
        from kafka.admin import KafkaAdminClient
        
        # Check if we can create a Kafka admin client
        logger.info("Testing Kafka connection with admin client...")
        admin_client = KafkaAdminClient(
            bootstrap_servers=bootstrap_servers,
            client_id='kafka-diagnosis',
            request_timeout_ms=5000
        )
        
        # List topics
        topics = admin_client.list_topics()
        logger.info(f"Available Kafka topics: {topics}")
        
        # Check if topic exists
        if topic in topics:
            logger.info(f"Topic {topic} exists")
        else:
            logger.warning(f"Topic {topic} does not exist")
            
        # Check consumer groups
        logger.info("Listing consumer groups...")
        consumer_groups = admin_client.list_consumer_groups()
        logger.info(f"Consumer groups: {consumer_groups}")
        
        # Test producer connection
        logger.info("Testing producer connection...")
        producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            client_id='kafka-diagnosis-producer',
            request_timeout_ms=5000
        )
        producer.close()
        logger.info("Producer connection successful")
        
        # Test consumer connection
        logger.info("Testing consumer connection...")
        consumer = KafkaConsumer(
            bootstrap_servers=bootstrap_servers,
            group_id='kafka-diagnosis-consumer',
            auto_offset_reset='earliest',
            client_id='kafka-diagnosis-consumer',
            request_timeout_ms=5000
        )
        consumer.close()
        logger.info("Consumer connection successful")
        
        return {
            "status": "success",
            "topics": topics,
            "consumer_groups": consumer_groups
        }
    except Exception as e:
        logger.error(f"Kafka diagnosis failed: {e}")
        return {
            "status": "error",
            "error": str(e)
        }

def get_consumer_status(consumer: Any) -> dict:
    """
    Get detailed information about consumer status.
    
    Args:
        consumer: The Kafka consumer adapter
        
    Returns:
        A dictionary with consumer status information
    """
    status = {
        "running": consumer._running if hasattr(consumer, '_running') else False,
        "subscribed_topics": list(consumer._subscribed_topics) if hasattr(consumer, '_subscribed_topics') else [],
        "handlers": {topic: len(handlers) for topic, handlers in consumer._handlers.items()} if hasattr(consumer, '_handlers') else {},
        "consumer_initialized": consumer._consumer is not None if hasattr(consumer, '_consumer') else False
    }
    
    # Get more details if the consumer is initialized
    if status["consumer_initialized"] and consumer._consumer:
        try:
            status["bootstrap_connected"] = consumer._consumer.bootstrap_connected
        except:
            status["bootstrap_connected"] = "unknown"
            
        try:  
            status["consumer_group"] = consumer.group_id
        except:
            status["consumer_group"] = "unknown"
    
    return status
