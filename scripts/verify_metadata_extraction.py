#!/usr/bin/env python
"""
Script to verify the metadata extraction flow in the RAG microservices architecture.
This script sends a metadata extraction request and checks for the processing result.

Usage:
    python verify_metadata_extraction.py [--bootstrap-server BOOTSTRAP_SERVER]
"""

import os
import json
import logging
import uuid
import time
import argparse
import requests
import asyncio
from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Default values
DEFAULT_BOOTSTRAP_SERVER = "localhost:9092"
DEFAULT_REQUEST_TOPIC = "metadata_extraction"  
DEFAULT_EVENTS_TOPIC = "document_events"
DEFAULT_LLM_SERVICE_URL = "http://localhost:8001"
DEFAULT_DOC_SERVICE_URL = "http://localhost:8002"
DEFAULT_TIMEOUT_SECONDS = 30

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Verify the metadata extraction flow in the microservices architecture.')
    parser.add_argument('--bootstrap-server', 
                        default=os.getenv('KAFKA_BOOTSTRAP_SERVERS', DEFAULT_BOOTSTRAP_SERVER),
                        help=f'Kafka bootstrap server (default: {DEFAULT_BOOTSTRAP_SERVER})')
    parser.add_argument('--request-topic', 
                        default=DEFAULT_REQUEST_TOPIC,
                        help=f'Kafka topic for metadata requests (default: {DEFAULT_REQUEST_TOPIC})')
    parser.add_argument('--events-topic', 
                        default=DEFAULT_EVENTS_TOPIC,
                        help=f'Kafka topic for document events (default: {DEFAULT_EVENTS_TOPIC})')
    parser.add_argument('--llm-service-url', 
                        default=os.getenv('LLM_SERVICE_URL', DEFAULT_LLM_SERVICE_URL),
                        help=f'URL of the LLM Service (default: {DEFAULT_LLM_SERVICE_URL})')
    parser.add_argument('--document-service-url', 
                        default=os.getenv('DOCUMENT_SERVICE_URL', DEFAULT_DOC_SERVICE_URL),
                        help=f'URL of the Document Service (default: {DEFAULT_DOC_SERVICE_URL})')
    parser.add_argument('--timeout', 
                        type=int,
                        default=DEFAULT_TIMEOUT_SECONDS,
                        help=f'Timeout in seconds for waiting for a response (default: {DEFAULT_TIMEOUT_SECONDS})')
    return parser.parse_args()

def check_metadata_consumer_status(llm_service_url):
    """Check the status of the metadata consumer in the LLM Service."""
    try:
        response = requests.get(f"{llm_service_url}/metadata/status", timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"Failed to get status: {response.status_code}", "running": False}
    except Exception as e:
        return {"error": str(e), "running": False}

def send_metadata_extraction_request(bootstrap_servers, topic, document_id):
    """Send a metadata extraction request to the metadata_extraction Kafka topic."""
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
                "source": "verify_script"
            }
        }
        
        logger.info(f"Sending metadata extraction request to topic '{topic}' for document_id: {document_id}")
        
        # Send the message
        future = producer.send(topic, message)
        producer.flush()
        
        # Wait for the send to complete
        record_metadata = future.get(timeout=10)
        logger.info(f"Message sent successfully to {record_metadata.topic} partition {record_metadata.partition}, offset {record_metadata.offset}")
        
        return {
            "status": "success",
            "correlation_id": correlation_id,
            "topic": record_metadata.topic,
            "partition": record_metadata.partition,
            "offset": record_metadata.offset
        }
        
    except Exception as e:
        logger.error(f"Error while sending message: {e}")
        return {"status": "error", "error": str(e)}
    finally:
        if 'producer' in locals():
            producer.close()

def wait_for_metadata_result(bootstrap_servers, topic, document_id, timeout_seconds):
    """
    Wait for a metadata extraction result on the document_events Kafka topic.
    Returns the result message or None if timeout occurs.
    """
    try:
        # Create Kafka consumer
        consumer = KafkaConsumer(
            topic,
            bootstrap_servers=bootstrap_servers,
            group_id=f'metadata-verification-{uuid.uuid4()}',  # Unique group to get all messages
            auto_offset_reset='latest',
            value_deserializer=lambda v: json.loads(v.decode('utf-8')),
            consumer_timeout_ms=1000  # 1 second timeout for each poll
        )
        
        logger.info(f"Waiting up to {timeout_seconds} seconds for metadata processing result...")
        
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            # Poll for messages
            messages = consumer.poll(timeout_ms=1000)
            
            for tp, records in messages.items():
                for record in records:
                    try:
                        # Check if this is a message for our document
                        if (record.value.get("payload", {}).get("documentId") == document_id and
                            record.value.get("payload", {}).get("status") in ["metadata_extracted", "failed"]):
                            
                            status = record.value.get("payload", {}).get("status")
                            if status == "metadata_extracted":
                                logger.info(f"Metadata extraction completed successfully for document {document_id}")
                                return record.value
                            elif status == "failed":
                                logger.error(f"Metadata extraction failed for document {document_id}")
                                return record.value
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
            
            # Small sleep to avoid CPU spinning
            time.sleep(0.5)
        
        logger.warning(f"Timed out waiting for metadata result after {timeout_seconds} seconds")
        return None
        
    except Exception as e:
        logger.error(f"Error while waiting for result: {e}")
        return None
    finally:
        if 'consumer' in locals():
            consumer.close()

def main():
    """Main execution function."""
    args = parse_arguments()
    
    # Step 1: Check if the metadata consumer is running
    logger.info("Checking if metadata consumer is running...")
    status = check_metadata_consumer_status(args.llm_service_url)
    
    if not status.get("running", False):
        logger.error(f"Metadata consumer is not running: {status.get('error', 'Unknown error')}")
        return 1
    
    logger.info(f"Metadata consumer is running. Status: {status}")
    
    # Step 2: Create a unique test document ID
    document_id = str(uuid.uuid4())
    logger.info(f"Created test document ID: {document_id}")
    
    # Step 3: Send metadata extraction request
    logger.info("Sending metadata extraction request...")
    send_result = send_metadata_extraction_request(
        bootstrap_servers=args.bootstrap_server,
        topic=args.request_topic,
        document_id=document_id
    )
    
    if send_result["status"] != "success":
        logger.error(f"Failed to send metadata extraction request: {send_result.get('error', 'Unknown error')}")
        return 1
    
    logger.info("Metadata extraction request sent successfully")
    
    # Step 4: Wait for the metadata extraction result
    logger.info("Waiting for metadata extraction result...")
    result = wait_for_metadata_result(
        bootstrap_servers=args.bootstrap_server,
        topic=args.events_topic,
        document_id=document_id,
        timeout_seconds=args.timeout
    )
    
    if not result:
        logger.error("No metadata extraction result received within the timeout period")
        return 1
    
    # Step 5: Print results and summary
    print("\n=== Metadata Extraction Verification Results ===")
    
    status = result.get("payload", {}).get("status")
    metadata = result.get("payload", {}).get("metadata", {})
    
    print(f"Document ID: {document_id}")
    print(f"Status: {status}")
    
    if status == "metadata_extracted":
        print("\nExtracted Metadata:")
        if metadata.get("extracted_metadata"):
            for key, value in metadata.get("extracted_metadata").items():
                print(f"  {key}: {value}")
        else:
            print("  No structured metadata found")
            
        print(f"\nEmbedding: {'Created successfully' if metadata.get('metadata_embedding') else 'Missing'}")
        print(f"Extraction Timestamp: {metadata.get('extraction_timestamp', 'Not provided')}")
        
        return 0
    else:
        print(f"\nError: {metadata.get('error', 'Unknown error')}")
        print(f"Stage: {metadata.get('stage', 'Unknown')}")
        print(f"Timestamp: {metadata.get('timestamp', 'Not provided')}")
        
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
