#!/usr/bin/env python
"""
Script to test the metadata extraction flow in the RAG microservices architecture.
This script sends test messages to the metadata_extraction Kafka topic.

Usage:
    python test_metadata_extraction.py [--bootstrap-server BOOTSTRAP_SERVER] [--document-id DOCUMENT_ID]
"""

import os
import json
import logging
import uuid
import argparse
from kafka import KafkaProducer
from kafka.errors import KafkaError

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Default values
DEFAULT_BOOTSTRAP_SERVER = "localhost:9092"
DEFAULT_TOPIC = "metadata_extraction"  # The correct topic for metadata extraction requests

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Test the metadata extraction flow by sending messages to Kafka.')
    parser.add_argument('--bootstrap-server', 
                        default=os.getenv('KAFKA_BOOTSTRAP_SERVERS', DEFAULT_BOOTSTRAP_SERVER),
                        help=f'Kafka bootstrap server (default: {DEFAULT_BOOTSTRAP_SERVER})')
    parser.add_argument('--topic', 
                        default=DEFAULT_TOPIC,
                        help=f'Kafka topic to send messages to (default: {DEFAULT_TOPIC})')
    parser.add_argument('--document-id', 
                        help='Optional: Specific document ID to use (defaults to random UUID)')
    return parser.parse_args()

def send_metadata_extraction_request(bootstrap_servers, topic, document_id=None):
    """Send a metadata extraction request to the Kafka topic."""
    try:
        # Create Kafka producer
        logger.info(f"Connecting to Kafka at {bootstrap_servers}")
        producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            api_version_auto_timeout_ms=5000,
            request_timeout_ms=10000,
            max_block_ms=10000
        )
        
        # Create a test document ID if not provided
        if not document_id:
            document_id = str(uuid.uuid4())
            
        # Create the message envelope
        correlation_id = str(uuid.uuid4())
        message = {
            "payload": {
                "documentId": document_id,
                "documentPath": f"storage/documents/{document_id}.pdf",
                "fileType": "application/pdf",
                "status": "metadata_requested",
                "priority": 5
            },
            "metadata": {
                "correlationId": correlation_id,
                "timestamp": str(uuid.utcnow().isoformat()),
                "source": "test_script"
            }
        }
        
        logger.info(f"Sending metadata extraction request to topic '{topic}' for document_id: {document_id}")
        logger.info(f"Message content: {json.dumps(message, indent=2)}")
        
        # Send the message
        future = producer.send(topic, message)
        producer.flush()
        
        # Wait for the send to complete
        record_metadata = future.get(timeout=10)
        logger.info(f"Message sent successfully to {record_metadata.topic} partition {record_metadata.partition}, offset {record_metadata.offset}")
        
        return {
            "status": "success",
            "message": "Metadata extraction request sent successfully",
            "document_id": document_id,
            "correlation_id": correlation_id,
            "topic": record_metadata.topic,
            "partition": record_metadata.partition,
            "offset": record_metadata.offset
        }
        
    except KafkaError as e:
        logger.error(f"Kafka error while sending message: {e}")
        return {
            "status": "error",
            "message": f"Kafka error: {str(e)}",
            "document_id": document_id
        }
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {
            "status": "error",
            "message": f"Unexpected error: {str(e)}",
            "document_id": document_id
        }
    finally:
        if 'producer' in locals():
            producer.close()

def main():
    """Main execution function."""
    args = parse_arguments()
    
    result = send_metadata_extraction_request(
        bootstrap_servers=args.bootstrap_server,
        topic=args.topic,
        document_id=args.document_id
    )
    
    # Print summary
    print("\n=== Metadata Extraction Test Summary ===")
    for key, value in result.items():
        print(f"{key}: {value}")
    
    return 0 if result["status"] == "success" else 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
