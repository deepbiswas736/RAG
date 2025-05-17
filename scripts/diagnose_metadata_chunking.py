#!/usr/bin/env python3
"""
Diagnostic script for metadata extraction and chunking services
==============================================================

This script diagnoses issues with the metadata extraction and chunking services
in the RAG system. It performs:

1. Container health checks
2. Document upload tests
3. Chunking verification
4. Metadata extraction verification
5. Connectivity tests between services

Run this script with:
    python diagnose_metadata_chunking.py [--test-upload /path/to/test/document.pdf]
"""

import os
import sys
import json
import time
import logging
import argparse
import asyncio
import subprocess
from typing import Dict, List, Any, Optional, Tuple
import requests
import aiohttp
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f"metadata_chunking_diagnosis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    ]
)
logger = logging.getLogger("metadata_chunking_diagnosis")

# Constants
DOCUMENT_SERVICE_URL = "http://localhost:80/api/v1/documents"
QUERY_SERVICE_URL = "http://localhost:80/api/v1/queries"
METADATA_SERVICE_URL = "http://localhost:80/api/v1/metadata"
KAFKA_TOPIC_DOCUMENT = "document-processed"
KAFKA_TOPIC_METADATA = "metadata-extraction"
MONGODB_URI = "mongodb://user:password@localhost:27017/?authSource=admin&replicaSet=rs0"

class DiagnosticTool:
    """Tool for diagnosing issues with metadata extraction and chunking"""
    
    def __init__(self):
        """Initialize the diagnostic tool"""
        self.results = {
            "container_health": {},
            "kafka_topics": {},
            "mongodb_status": {},
            "document_upload": {},
            "chunking": {},
            "metadata_extraction": {},
            "connectivity": {}
        }
        self.test_document_id = None
    
    async def run_diagnostics(self, test_document_path=None):
        """Run all diagnostic tests"""
        logger.info("Starting diagnostic tests...")
        
        # Check container health
        await self.check_container_health()
        
        # Check MongoDB status
        await self.check_mongodb_status()
        
        # Check Kafka topics
        await self.check_kafka_topics()
        
        # Test document upload if file provided
        if test_document_path and os.path.exists(test_document_path):
            await self.test_document_upload(test_document_path)
            
            # Only run these tests if document upload succeeded
            if self.test_document_id:
                # Check chunking
                await self.check_chunking()
                
                # Check metadata extraction
                await self.check_metadata_extraction()
        else:
            logger.warning("No test document provided or file not found. Skipping document upload tests.")
            
        # Check connectivity between services
        await self.check_service_connectivity()
        
        # Print diagnostic summary
        self.print_diagnostic_summary()
        
        # Save results to file
        self.save_results()
    
    async def check_container_health(self):
        """Check the health of all containers"""
        logger.info("Checking container health...")
        
        try:
            # Get list of running containers 
            result = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}"],
                capture_output=True, text=True
            )
            
            containers = {}
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split('\t')
                    if len(parts) == 2:
                        name, status = parts
                        containers[name] = status
            
            # Check required containers
            required_containers = [
                "rag_document-service", "rag_llm-service", 
                "rag_query-service", "rag_mongodb", "rag_kafka",
                "rag_traefik"
            ]
            
            container_status = {}
            missing_containers = []
            
            for container in required_containers:
                for actual_name, status in containers.items():
                    if container in actual_name:
                        container_status[container] = {
                            "status": status,
                            "running": "Up" in status
                        }
                        break
                else:
                    missing_containers.append(container)
                    container_status[container] = {
                        "status": "Not found",
                        "running": False
                    }
            
            self.results["container_health"] = {
                "status": "OK" if not missing_containers else "PROBLEM",
                "missing_containers": missing_containers,
                "containers": container_status
            }
                
            if missing_containers:
                logger.warning(f"Missing containers: {', '.join(missing_containers)}")
            else:
                logger.info("All required containers are running")
                
        except Exception as e:
            logger.exception("Error checking container health")
            self.results["container_health"] = {
                "status": "ERROR",
                "error": str(e)
            }
    
    async def check_mongodb_status(self):
        """Check MongoDB status and replica set configuration"""
        logger.info("Checking MongoDB status...")
        
        try:
            # Run MongoDB status check script
            result = subprocess.run(
                ["python", "e:/code/experimental/RAG/scripts/check_mongodb_status.ps1"],
                capture_output=True, text=True
            )
            
            # Parse output
            output = result.stdout.strip()
            is_healthy = "Replica set is healthy" in output
            
            self.results["mongodb_status"] = {
                "status": "OK" if is_healthy else "PROBLEM",
                "details": output,
                "error": result.stderr if result.returncode != 0 else None
            }
            
            if not is_healthy:
                logger.warning("MongoDB replica set is NOT healthy!")
            else:
                logger.info("MongoDB replica set is healthy")
                
        except Exception as e:
            logger.exception("Error checking MongoDB status")
            self.results["mongodb_status"] = {
                "status": "ERROR",
                "error": str(e)
            }
    
    async def check_kafka_topics(self):
        """Check Kafka topics and messages"""
        logger.info("Checking Kafka topics...")
        
        try:
            # Run Kafka check script
            result = subprocess.run(
                ["python", "e:/code/experimental/RAG/scripts/check_kafka_topics.py"],
                capture_output=True, text=True
            )
            
            # Parse output
            output = result.stdout.strip()
            
            # Extract topic info
            topic_info = {}
            for line in output.split('\n'):
                if ':' in line:
                    topic, info = line.split(':', 1)
                    topic = topic.strip()
                    topic_info[topic] = info.strip()
            
            self.results["kafka_topics"] = {
                "status": "OK" if KAFKA_TOPIC_DOCUMENT in topic_info and KAFKA_TOPIC_METADATA in topic_info else "PROBLEM",
                "topics": topic_info
            }
            
            # Check for required topics
            missing_topics = []
            for required_topic in [KAFKA_TOPIC_DOCUMENT, KAFKA_TOPIC_METADATA]:
                if required_topic not in topic_info:
                    missing_topics.append(required_topic)
            
            if missing_topics:
                logger.warning(f"Missing Kafka topics: {', '.join(missing_topics)}")
                self.results["kafka_topics"]["missing_topics"] = missing_topics
            else:
                logger.info("All required Kafka topics exist")
                
        except Exception as e:
            logger.exception("Error checking Kafka topics")
            self.results["kafka_topics"] = {
                "status": "ERROR",
                "error": str(e)
            }
    
    async def test_document_upload(self, document_path):
        """Test document upload functionality"""
        logger.info(f"Testing document upload with file: {document_path}")
        
        try:
            filename = os.path.basename(document_path)
            
            # Prepare files for upload
            files = {'file': (filename, open(document_path, 'rb'))}
            data = {'title': f'Test Document {datetime.now().strftime("%Y%m%d_%H%M%S")}'}
            
            # Upload document
            response = requests.post(
                f"{DOCUMENT_SERVICE_URL}/upload",
                files=files,
                data=data
            )
            
            if response.status_code == 200:
                result = response.json()
                document_id = result.get("document_id")
                self.test_document_id = document_id
                
                logger.info(f"Document uploaded successfully. ID: {document_id}")
                
                self.results["document_upload"] = {
                    "status": "OK",
                    "document_id": document_id,
                    "response": result
                }
                
                # Wait for processing to complete
                logger.info("Waiting for document processing to complete...")
                await asyncio.sleep(10)
                
            else:
                logger.warning(f"Document upload failed. Status code: {response.status_code}")
                self.results["document_upload"] = {
                    "status": "FAILED",
                    "status_code": response.status_code,
                    "response": response.text
                }
                
        except Exception as e:
            logger.exception("Error uploading document")
            self.results["document_upload"] = {
                "status": "ERROR",
                "error": str(e)
            }
    
    async def check_chunking(self):
        """Check if document chunking is working properly"""
        if not self.test_document_id:
            logger.warning("No test document ID available. Skipping chunking check.")
            self.results["chunking"] = {
                "status": "SKIPPED",
                "reason": "No test document ID available"
            }
            return
        
        logger.info(f"Checking chunking for document ID: {self.test_document_id}")
        
        try:
            # Try to get chunks for the document
            response = requests.get(
                f"{DOCUMENT_SERVICE_URL}/{self.test_document_id}/chunks"
            )
            
            if response.status_code == 200:
                chunks = response.json()
                
                # Check if chunks exist
                if chunks and len(chunks) > 0:
                    logger.info(f"Document has {len(chunks)} chunks")
                    self.results["chunking"] = {
                        "status": "OK",
                        "chunk_count": len(chunks),
                        "sample_chunk": chunks[0] if chunks else None
                    }
                else:
                    logger.warning("Document has no chunks!")
                    self.results["chunking"] = {
                        "status": "PROBLEM",
                        "reason": "No chunks found for document"
                    }
            else:
                logger.warning(f"Failed to get document chunks. Status code: {response.status_code}")
                self.results["chunking"] = {
                    "status": "FAILED",
                    "status_code": response.status_code,
                    "response": response.text
                }
                
        except Exception as e:
            logger.exception("Error checking document chunking")
            self.results["chunking"] = {
                "status": "ERROR",
                "error": str(e)
            }
    
    async def check_metadata_extraction(self):
        """Check if metadata extraction is working properly"""
        if not self.test_document_id:
            logger.warning("No test document ID available. Skipping metadata extraction check.")
            self.results["metadata_extraction"] = {
                "status": "SKIPPED",
                "reason": "No test document ID available"
            }
            return
        
        logger.info(f"Checking metadata extraction for document ID: {self.test_document_id}")
        
        try:
            # Try to get metadata for the document
            response = requests.get(
                f"{DOCUMENT_SERVICE_URL}/{self.test_document_id}/metadata"
            )
            
            if response.status_code == 200:
                metadata = response.json()
                
                # Check if metadata exists
                if metadata and isinstance(metadata, dict) and len(metadata) > 0:
                    logger.info(f"Document has metadata with {len(metadata)} fields")
                    self.results["metadata_extraction"] = {
                        "status": "OK",
                        "field_count": len(metadata),
                        "metadata": metadata
                    }
                else:
                    logger.warning("Document has no metadata!")
                    self.results["metadata_extraction"] = {
                        "status": "PROBLEM",
                        "reason": "No metadata found for document"
                    }
            else:
                logger.warning(f"Failed to get document metadata. Status code: {response.status_code}")
                self.results["metadata_extraction"] = {
                    "status": "FAILED",
                    "status_code": response.status_code,
                    "response": response.text
                }
                
        except Exception as e:
            logger.exception("Error checking document metadata")
            self.results["metadata_extraction"] = {
                "status": "ERROR",
                "error": str(e)
            }
    
    async def check_service_connectivity(self):
        """Check connectivity between services"""
        logger.info("Checking service connectivity...")
        
        services = [
            ("document-service", "http://localhost:80/api/v1/documents/health"),
            ("query-service", "http://localhost:80/api/v1/queries/health"),
            ("llm-service", "http://localhost:80/api/v1/llm/health")
        ]
        
        connectivity = {}
        
        for service_name, health_url in services:
            try:
                response = requests.get(health_url, timeout=5)
                
                if response.status_code == 200:
                    logger.info(f"{service_name} is healthy and reachable")
                    connectivity[service_name] = {
                        "status": "OK",
                        "response": response.json() if response.headers.get('content-type') == 'application/json' else response.text
                    }
                else:
                    logger.warning(f"{service_name} returned status code {response.status_code}")
                    connectivity[service_name] = {
                        "status": "PROBLEM",
                        "status_code": response.status_code,
                        "response": response.text
                    }
            except requests.exceptions.RequestException as e:
                logger.warning(f"Cannot connect to {service_name}: {e}")
                connectivity[service_name] = {
                    "status": "ERROR",
                    "error": str(e)
                }
        
        self.results["connectivity"] = connectivity
    
    def print_diagnostic_summary(self):
        """Print a summary of the diagnostic results"""
        logger.info("\n" + "="*50)
        logger.info("DIAGNOSTIC SUMMARY")
        logger.info("="*50)
        
        # Container health
        container_health = self.results["container_health"]
        logger.info(f"\nContainer Health: {container_health.get('status', 'UNKNOWN')}")
        if container_health.get("status") != "OK":
            if "missing_containers" in container_health:
                logger.info(f"  Missing containers: {', '.join(container_health['missing_containers'])}")
        
        # MongoDB status
        mongodb_status = self.results["mongodb_status"]  
        logger.info(f"\nMongoDB Status: {mongodb_status.get('status', 'UNKNOWN')}")
        
        # Kafka topics
        kafka_topics = self.results["kafka_topics"]
        logger.info(f"\nKafka Topics: {kafka_topics.get('status', 'UNKNOWN')}")
        if kafka_topics.get("status") != "OK" and "missing_topics" in kafka_topics:
            logger.info(f"  Missing topics: {', '.join(kafka_topics['missing_topics'])}")
        
        # Document upload
        document_upload = self.results["document_upload"]
        logger.info(f"\nDocument Upload: {document_upload.get('status', 'UNKNOWN')}")
        
        # Chunking
        chunking = self.results["chunking"]
        logger.info(f"\nChunking: {chunking.get('status', 'UNKNOWN')}")
        if chunking.get("status") == "OK":
            logger.info(f"  Chunk count: {chunking.get('chunk_count', 0)}")
        
        # Metadata extraction
        metadata = self.results["metadata_extraction"]
        logger.info(f"\nMetadata Extraction: {metadata.get('status', 'UNKNOWN')}")
        if metadata.get("status") == "OK":
            logger.info(f"  Metadata fields: {metadata.get('field_count', 0)}")
        
        # Service connectivity
        logger.info("\nService Connectivity:")
        connectivity = self.results["connectivity"]
        for service, status in connectivity.items():
            logger.info(f"  {service}: {status.get('status', 'UNKNOWN')}")
        
        # Overall assessment
        problem_areas = [
            area for area, data in self.results.items() 
            if data.get("status", "") not in ["OK", "SKIPPED"]
        ]
        
        logger.info("\n" + "="*50)
        if problem_areas:
            logger.info(f"ISSUES DETECTED in: {', '.join(problem_areas)}")
        else:
            logger.info("NO ISSUES DETECTED - All systems functioning normally")
        logger.info("="*50 + "\n")

        # Recommendations
        logger.info("RECOMMENDATIONS:")
        self._generate_recommendations()
    
    def _generate_recommendations(self):
        """Generate recommendations based on diagnostic results"""
        container_health = self.results["container_health"]
        mongodb_status = self.results["mongodb_status"]
        kafka_topics = self.results["kafka_topics"]
        chunking = self.results["chunking"]
        metadata = self.results["metadata_extraction"]
        
        # Container health issues
        if container_health.get("status") != "OK":
            missing = container_health.get("missing_containers", [])
            if missing:
                logger.info(f"- Start the missing containers: {', '.join(missing)}")
                logger.info("  Use 'docker-compose up -d' to ensure all services are running")
        
        # MongoDB issues
        if mongodb_status.get("status") != "OK":
            logger.info("- Check MongoDB replica set configuration:")
            logger.info("  1. Verify the MongoDB container is running properly")
            logger.info("  2. Check if replica set was initialized correctly")
            logger.info("  3. Run 'docker exec -it rag_mongodb mongosh' to verify connectivity")
        
        # Kafka issues
        if kafka_topics.get("status") != "OK":
            if "missing_topics" in kafka_topics:
                logger.info(f"- Create missing Kafka topics: {', '.join(kafka_topics['missing_topics'])}")
                logger.info("  Topics must be created for proper message routing")
        
        # Chunking issues
        if chunking.get("status") not in ["OK", "SKIPPED"]:
            logger.info("- Check chunking configuration in document service:")
            logger.info("  1. Verify ChunkingService parameters (chunk size, overlap)")
            logger.info("  2. Check logs for chunking errors")
            logger.info("  3. Ensure chunking utilities like NLTK are properly installed")
        
        # Metadata issues
        if metadata.get("status") not in ["OK", "SKIPPED"]:
            logger.info("- Check metadata extraction service:")
            logger.info("  1. Verify LLM service is running and accessible")
            logger.info("  2. Check that metadata extraction Kafka topic exists")
            logger.info("  3. Check CPU and memory resources for LLM service")
            logger.info("  4. Verify connectivity between document service and LLM service")
    
    def save_results(self):
        """Save diagnostic results to a file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"metadata_chunking_diagnosis_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        logger.info(f"Diagnostic results saved to {filename}")


async def main():
    # Parse arguments
    parser = argparse.ArgumentParser(description="Diagnose metadata and chunking services")
    parser.add_argument(
        "--test-upload",
        help="Path to a test document to upload during diagnosis",
        default=None
    )
    args = parser.parse_args()
    
    # Run diagnostics
    tool = DiagnosticTool()
    await tool.run_diagnostics(args.test_upload)


if __name__ == "__main__":
    asyncio.run(main())
