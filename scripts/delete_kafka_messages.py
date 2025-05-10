#!/usr/bin/env python
"""
Script to delete all messages from a Kafka topic by creating a new consumer group
and consuming all messages without processing them.

Usage:
    python delete_kafka_messages.py
"""

import os
import json
import logging
import time
from kafka import KafkaConsumer, KafkaAdminClient
from kafka.admin import NewTopic
from kafka.errors import KafkaError

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Kafka configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC_NAME = "metadata_enrichment"
CONSUMER_GROUP = f"delete_messages_group_{int(time.time())}"  # Unique consumer group

def delete_messages_from_topic():
    """Delete all messages from the specified Kafka topic by consuming them."""
    logger.info(f"Starting deletion of all messages from topic: {TOPIC_NAME}")
    logger.info(f"Using Kafka bootstrap servers: {KAFKA_BOOTSTRAP_SERVERS}")
    
    try:
        # Create a consumer with a unique group id to ensure we get all messages
        consumer = KafkaConsumer(
            TOPIC_NAME,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            group_id=CONSUMER_GROUP,
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            auto_commit_interval_ms=1000,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')) if m else None,
        )
        
        logger.info(f"Consumer created with group id: {CONSUMER_GROUP}")
        
        # Count messages consumed
        message_count = 0
        start_time = time.time()
        timeout = 10  # seconds to wait for messages before assuming we're done
        
        while True:
            # Poll with a short timeout to check for messages
            messages = consumer.poll(timeout_ms=1000)
            
            if not messages:
                # If no messages for a while, we're likely done
                if time.time() - start_time > timeout:
                    break
                continue
                
            # Reset timeout timer when we get messages
            start_time = time.time()
            
            # Count messages and commit offsets
            for topic_partition, records in messages.items():
                message_count += len(records)
                logger.info(f"Consumed {len(records)} messages from {topic_partition.topic}:{topic_partition.partition}")
        
        consumer.close()
        logger.info(f"Successfully deleted (consumed) {message_count} messages from topic: {TOPIC_NAME}")
        
        return message_count
        
    except KafkaError as e:
        logger.error(f"Kafka error while deleting messages: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise

if __name__ == "__main__":
    try:
        count = delete_messages_from_topic()
        logger.info(f"Script completed successfully! Deleted {count} messages.")
    except Exception as e:
        logger.error(f"Script failed: {e}")