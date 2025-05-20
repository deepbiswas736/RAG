"""
Kafka Health Check

This module provides utilities for checking Kafka health and diagnosing issues.
"""

import logging
import asyncio
import json
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

async def check_kafka_health(bootstrap_servers: str) -> Dict[str, Any]:
    """
    Check Kafka health by testing connectivity, listing topics, and consumer groups.
    
    Args:
        bootstrap_servers: Comma-separated list of Kafka bootstrap servers
        
    Returns:
        Dict with health check results
    """
    results = {
        "bootstrap_servers": bootstrap_servers,
        "connected": False,
        "topics": [],
        "consumer_groups": []
    }
    
    try:
        # Import Kafka libraries here to avoid circular imports
        from aiokafka import AIOKafkaProducer
        from aiokafka.admin import AIOKafkaAdminClient
        
        # Check connectivity with a producer
        logger.info(f"Testing Kafka connection to {bootstrap_servers}")
        producer = AIOKafkaProducer(bootstrap_servers=bootstrap_servers)
        await producer.start()
        results["connected"] = True
        await producer.stop()
        
        # List topics
        admin_client = AIOKafkaAdminClient(bootstrap_servers=bootstrap_servers)
        await admin_client.start()
        topics = await admin_client.list_topics()
        results["topics"] = list(topics)
        
        # Describe consumer groups
        # This requires using the kafka-python library as aiokafka doesn't have this functionality
        from kafka.admin import KafkaAdminClient
        sync_admin = KafkaAdminClient(bootstrap_servers=bootstrap_servers)
        consumer_groups = sync_admin.list_consumer_groups()
        results["consumer_groups"] = consumer_groups
        
        await admin_client.close()
        
        return results
    except Exception as e:
        logger.error(f"Failed to check Kafka health: {e}", exc_info=True)
        results["error"] = str(e)
        return results

async def fix_consumer_issues(bootstrap_servers: str, topic: str, consumer_group: str) -> Dict[str, Any]:
    """
    Attempt to fix common Kafka consumer issues.
    
    Args:
        bootstrap_servers: Comma-separated list of Kafka bootstrap servers
        topic: Topic name
        consumer_group: Consumer group ID
        
    Returns:
        Dict with fix results
    """
    results = {
        "topic": topic,
        "consumer_group": consumer_group,
        "actions_taken": []
    }
    
    try:
        # Check if topic exists
        from aiokafka.admin import AIOKafkaAdminClient, NewTopic
        admin_client = AIOKafkaAdminClient(bootstrap_servers=bootstrap_servers)
        await admin_client.start()
        
        topics = await admin_client.list_topics()
        if topic not in topics:
            # Create topic
            logger.info(f"Topic {topic} doesn't exist. Creating it...")
            await admin_client.create_topics([
                NewTopic(
                    name=topic, 
                    num_partitions=1, 
                    replication_factor=1
                )
            ])
            results["actions_taken"].append(f"Created topic {topic}")
        
        await admin_client.close()
        
        # Check consumer group
        # Using kafka-python for consumer group operations
        from kafka.admin import KafkaAdminClient
        sync_admin = KafkaAdminClient(bootstrap_servers=bootstrap_servers)
        consumer_groups = sync_admin.list_consumer_groups()
        
        group_found = False
        for group, type in consumer_groups:
            if group == consumer_group:
                group_found = True
                break
        
        if not group_found:
            results["actions_taken"].append(f"Consumer group {consumer_group} not found. Will be created when consumer connects.")
            
        # Send a test message to the topic
        try:
            from aiokafka import AIOKafkaProducer
            producer = AIOKafkaProducer(bootstrap_servers=bootstrap_servers)
            await producer.start()
            
            test_message = {
                "test": True,
                "message": "Kafka connectivity test",
                "timestamp": int(asyncio.get_event_loop().time())
            }
            
            await producer.send_and_wait(
                topic, 
                json.dumps(test_message).encode('utf-8')
            )
            
            await producer.stop()
            results["actions_taken"].append(f"Sent test message to {topic}")
        except Exception as e:
            logger.error(f"Failed to send test message: {e}")
            results["actions_taken"].append(f"Failed to send test message: {str(e)}")
        
        return results
    except Exception as e:
        logger.error(f"Failed to fix consumer issues: {e}", exc_info=True)
        results["error"] = str(e)
        return results
