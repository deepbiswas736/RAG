#!/usr/bin/env python
"""
Script to check if required Kafka topics exist and create them if they don't.

Usage:
    python check_kafka_topics.py [--bootstrap-server BOOTSTRAP_SERVER] [--create]

Arguments:
    --bootstrap-server  Kafka bootstrap server (default: localhost:9092)
    --create            Create missing topics (default: True)
"""

import os
import sys
import logging
import argparse
from kafka import KafkaAdminClient
from kafka.admin import NewTopic, ConfigResource, ConfigResourceType
from kafka.errors import KafkaError, TopicAlreadyExistsError, UnknownTopicOrPartitionError

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_BOOTSTRAP_SERVER = "localhost:9092"
REQUIRED_TOPICS = [
    {"name": "rag_queries", "partitions": 1, "replication_factor": 1},
    {"name": "metadata_enrichment", "partitions": 1, "replication_factor": 1},
]

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Check and create Kafka topics.')
    parser.add_argument('--bootstrap-server', 
                        default=os.getenv('KAFKA_BOOTSTRAP_SERVERS', DEFAULT_BOOTSTRAP_SERVER),
                        help=f'Kafka bootstrap server (default: {DEFAULT_BOOTSTRAP_SERVER})')
    parser.add_argument('--create', 
                        action='store_true',
                        default=True,
                        help='Create missing topics (default: True)')
    return parser.parse_args()

def check_and_create_topics(bootstrap_server, create_missing=True):
    """
    Check if required topics exist and create them if they don't.
    
    Args:
        bootstrap_server (str): Kafka bootstrap server address
        create_missing (bool): Whether to create missing topics
        
    Returns:
        tuple: (existing_topics, missing_topics, created_topics)
    """
    logger.info(f"Connecting to Kafka at {bootstrap_server}")
    
    try:
        # Create Kafka admin client
        admin_client = KafkaAdminClient(
            bootstrap_servers=bootstrap_server,
            client_id='rag-topic-checker'
        )
        
        # Get existing topics
        try:
            existing_topics = admin_client.list_topics()
            logger.info(f"Found {len(existing_topics)} topics in Kafka")
        except KafkaError as e:
            logger.error(f"Failed to list topics: {e}")
            return [], [], []
            
        # Check which required topics are missing
        missing_topics = []
        for topic_config in REQUIRED_TOPICS:
            topic_name = topic_config["name"]
            if topic_name not in existing_topics:
                missing_topics.append(topic_config)
                logger.warning(f"Topic '{topic_name}' does not exist")
            else:
                logger.info(f"Topic '{topic_name}' exists")
        
        # Create missing topics if requested
        created_topics = []
        if missing_topics and create_missing:
            logger.info(f"Creating {len(missing_topics)} missing topics")
            
            for topic_config in missing_topics:
                topic_name = topic_config["name"]
                partitions = topic_config["partitions"]
                replication_factor = topic_config["replication_factor"]
                
                try:
                    new_topic = NewTopic(
                        name=topic_name,
                        num_partitions=partitions,
                        replication_factor=replication_factor
                    )
                    admin_client.create_topics([new_topic])
                    created_topics.append(topic_name)
                    logger.info(f"Created topic '{topic_name}' with {partitions} partition(s) and replication factor {replication_factor}")
                except TopicAlreadyExistsError:
                    logger.warning(f"Topic '{topic_name}' already exists (race condition)")
                except Exception as e:
                    logger.error(f"Failed to create topic '{topic_name}': {e}")
        
        # Clean up
        admin_client.close()
        
        return existing_topics, missing_topics, created_topics
        
    except Exception as e:
        logger.error(f"Error connecting to Kafka: {e}")
        return [], [], []

def main():
    """Main execution function."""
    args = parse_arguments()
    
    try:
        existing, missing, created = check_and_create_topics(
            args.bootstrap_server, 
            create_missing=args.create
        )
        
        # Print summary
        print("\n=== Kafka Topic Summary ===")
        print(f"Bootstrap Server: {args.bootstrap_server}")
        print(f"Existing Topics: {len(existing)}")
        
        if existing:
            print("\nExisting Topics:")
            for topic in existing:
                print(f"  - {topic}")
        
        if missing:
            print("\nMissing Topics:")
            for topic in missing:
                status = "Created" if topic["name"] in created else "Not Created"
                print(f"  - {topic['name']} ({status})")
                
        if created:
            print(f"\nCreated {len(created)} missing topic(s)")
        
        # Return success status
        return 0 if not missing or len(created) == len(missing) else 1
        
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())