#!/usr/bin/env python3
"""
Test Script for Metadata and Chunking
====================================

This script provides direct testing for both metadata extraction and
document chunking individually, allowing for focused troubleshooting.

Usage:
    python test_metadata_chunking.py
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
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

class ServiceTester:
    """Test metadata and chunking services individually"""
    
    def __init__(self):
        self.base_url = "http://localhost:80/api/v1"
        self.document_id = None
        self.test_file_path = None
    
    async def test_menu(self):
        """Show interactive test menu"""
        while True:
            self._clear_screen()
            print("\n=== METADATA & CHUNKING SERVICE TESTER ===\n")
            print("Current document ID:", self.document_id or "None")
            print("Current test file:", self.test_file_path or "None")
            print("\nOptions:")
            print("1. Set test document ID")
            print("2. Upload new test document")
            print("3. Test document chunking")
            print("4. Test metadata extraction")
            print("5. Check service status")
            print("6. Check logs for errors")
            print("7. Test direct API endpoints")
            print("8. Exit")
            
            choice = input("\nEnter your choice (1-8): ")
            
            if choice == "1":
                await self._set_document_id()
            elif choice == "2":
                await self._upload_document()
            elif choice == "3":
                await self._test_chunking()
            elif choice == "4":
                await self._test_metadata()
            elif choice == "5":
                await self._check_service_status()
            elif choice == "6":
                await self._check_logs()
            elif choice == "7":
                await self._test_direct_api()
            elif choice == "8":
                print("Exiting...")
                break
            else:
                print("Invalid choice. Press enter to continue...")
                input()
    
    def _clear_screen(self):
        """Clear the screen"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    async def _set_document_id(self):
        """Set the document ID for testing"""
        self._clear_screen()
        print("\n=== SET DOCUMENT ID ===\n")
        
        document_id = input("Enter document ID: ").strip()
        if document_id:
            self.document_id = document_id
            print(f"Document ID set to: {document_id}")
        else:
            print("Document ID cannot be empty")
        
        input("\nPress enter to continue...")
    
    async def _upload_document(self):
        """Upload a new test document"""
        self._clear_screen()
        print("\n=== UPLOAD TEST DOCUMENT ===\n")
        
        file_path = input("Enter path to document file: ").strip()
        
        if not file_path or not os.path.exists(file_path):
            print("File not found or invalid path")
            input("\nPress enter to continue...")
            return
        
        self.test_file_path = file_path
        filename = os.path.basename(file_path)
        
        try:
            # Prepare files for upload
            files = {'file': (filename, open(file_path, 'rb'))}
            data = {'title': f'Test Document {datetime.now().strftime("%Y%m%d_%H%M%S")}'}
            
            print(f"Uploading document: {filename}...")
            
            # Upload document
            response = requests.post(
                f"{self.base_url}/documents/upload",
                files=files,
                data=data
            )
            
            if response.status_code == 200:
                result = response.json()
                document_id = result.get("document_id")
                self.document_id = document_id
                
                print(f"Document uploaded successfully. ID: {document_id}")
                print(f"Response: {json.dumps(result, indent=2)}")
            else:
                print(f"Document upload failed. Status code: {response.status_code}")
                print(f"Error: {response.text}")
                
        except Exception as e:
            print(f"Error uploading document: {str(e)}")
        
        input("\nPress enter to continue...")
    
    async def _test_chunking(self):
        """Test document chunking"""
        self._clear_screen()
        print("\n=== TEST DOCUMENT CHUNKING ===\n")
        
        if not self.document_id:
            print("No document ID set. Please set a document ID first.")
            input("\nPress enter to continue...")
            return
        
        try:
            print(f"Testing chunking for document ID: {self.document_id}")
            
            # Try to get chunks for the document
            response = requests.get(
                f"{self.base_url}/documents/{self.document_id}/chunks"
            )
            
            if response.status_code == 200:
                chunks = response.json()
                
                # Check if chunks exist
                if chunks and len(chunks) > 0:
                    print(f"Document has {len(chunks)} chunks")
                    print("\nFirst chunk sample:")
                    print(json.dumps(chunks[0], indent=2)[:500] + "...")
                    print(f"\nLast chunk sample:")
                    print(json.dumps(chunks[-1], indent=2)[:500] + "...")
                else:
                    print("Document has no chunks!")
            else:
                print(f"Failed to get document chunks. Status code: {response.status_code}")
                print(f"Error: {response.text}")
                
            # Get raw chunk data from MongoDB for comparison
            print("\nChecking MongoDB for raw chunk data...")
            result = subprocess.run(
                ["python", "-c", f"import pymongo; client = pymongo.MongoClient('mongodb://user:password@localhost:27017/?authSource=admin'); db = client['document_db']; chunks = list(db.chunks.find({{'document_id': '{self.document_id}'}})); print(f'Found {{len(chunks)}} chunks in MongoDB'); client.close()"],
                capture_output=True, text=True
            )
            print(result.stdout)
            
        except Exception as e:
            print(f"Error checking document chunking: {str(e)}")
        
        input("\nPress enter to continue...")
    
    async def _test_metadata(self):
        """Test metadata extraction"""
        self._clear_screen()
        print("\n=== TEST METADATA EXTRACTION ===\n")
        
        if not self.document_id:
            print("No document ID set. Please set a document ID first.")
            input("\nPress enter to continue...")
            return
        
        try:
            print(f"Testing metadata extraction for document ID: {self.document_id}")
            
            # Try to get metadata for the document
            response = requests.get(
                f"{self.base_url}/documents/{self.document_id}/metadata"
            )
            
            if response.status_code == 200:
                metadata = response.json()
                
                # Check if metadata exists
                if metadata and isinstance(metadata, dict) and len(metadata) > 0:
                    print(f"Document has metadata with {len(metadata)} fields:")
                    print(json.dumps(metadata, indent=2))
                    
                    # Check metadata quality
                    if "metadata_quality" in metadata:
                        quality = metadata["metadata_quality"]
                        print(f"\nMetadata quality: {quality}")
                        if quality < 0.5:
                            print("WARNING: Metadata quality is low!")
                else:
                    print("Document has no metadata!")
            else:
                print(f"Failed to get document metadata. Status code: {response.status_code}")
                print(f"Error: {response.text}")
                
            # Check metadata extraction status
            print("\nChecking metadata extraction status in Kafka...")
            result = subprocess.run(
                ["python", "e:/code/experimental/RAG/scripts/check_kafka_topics.py", "metadata-extraction"],
                capture_output=True, text=True
            )
            print(result.stdout)
            
            # Get raw metadata from MongoDB for comparison
            print("\nChecking MongoDB for raw metadata...")
            result = subprocess.run(
                ["python", "-c", f"import pymongo; client = pymongo.MongoClient('mongodb://user:password@localhost:27017/?authSource=admin'); db = client['document_db']; doc = db.documents.find_one({{'id': '{self.document_id}'}}); print(f'Document metadata: {{doc.get(\"metadata\", {{}})}}'); client.close()"],
                capture_output=True, text=True
            )
            print(result.stdout)
                
        except Exception as e:
            print(f"Error checking document metadata: {str(e)}")
        
        input("\nPress enter to continue...")
    
    async def _check_service_status(self):
        """Check status of all services"""
        self._clear_screen()
        print("\n=== SERVICE STATUS ===\n")
        
        services = [
            ("Document Service", f"{self.base_url}/documents/health"),
            ("Query Service", f"{self.base_url}/queries/health"),
            ("LLM Service", f"{self.base_url}/llm/health")
        ]
        
        for service_name, health_url in services:
            try:
                print(f"Checking {service_name}...")
                response = requests.get(health_url, timeout=5)
                
                if response.status_code == 200:
                    print(f"  Status: HEALTHY (200 OK)")
                    try:
                        data = response.json()
                        print(f"  Details: {json.dumps(data, indent=2)}")
                    except:
                        print(f"  Response: {response.text}")
                else:
                    print(f"  Status: UNHEALTHY ({response.status_code})")
                    print(f"  Error: {response.text}")
            except requests.exceptions.RequestException as e:
                print(f"  Status: UNREACHABLE")
                print(f"  Error: {str(e)}")
                
            print()
        
        # Check MongoDB status
        print("Checking MongoDB...")
        try:
            result = subprocess.run(
                ["python", "-c", "import pymongo; client = pymongo.MongoClient('mongodb://user:password@localhost:27017/?authSource=admin'); info = client.server_info(); print(f'  MongoDB version: {info[\"version\"]}'); print(f'  Status: Connected'); client.close()"],
                capture_output=True, text=True
            )
            print(result.stdout)
        except Exception as e:
            print(f"  Status: ERROR")
            print(f"  Error: {str(e)}")
        
        # Check Kafka status
        print("\nChecking Kafka...")
        try:
            result = subprocess.run(
                ["python", "e:/code/experimental/RAG/scripts/check_kafka_topics.py"],
                capture_output=True, text=True
            )
            print(result.stdout)
        except Exception as e:
            print(f"  Status: ERROR")
            print(f"  Error: {str(e)}")
        
        input("\nPress enter to continue...")
    
    async def _check_logs(self):
        """Check logs for errors"""
        self._clear_screen()
        print("\n=== CHECK SERVICE LOGS ===\n")
        
        services = ["document-service", "llm-service", "query-service"]
        
        for service in services:
            print(f"Checking logs for {service}...")
            try:
                # Get container name from docker ps
                result = subprocess.run(
                    ["docker", "ps", "--format", "{{.Names}}", "--filter", f"name=rag_{service}"],
                    capture_output=True, text=True
                )
                container_name = result.stdout.strip()
                
                if container_name:
                    # Get logs with error/warning messages
                    result = subprocess.run(
                        ["docker", "logs", container_name, "--tail", "50"],
                        capture_output=True, text=True
                    )
                    
                    # Filter for error and warning messages
                    log_lines = result.stdout.strip().split("\n")
                    error_logs = [line for line in log_lines if "ERROR" in line or "error" in line.lower()]
                    warning_logs = [line for line in log_lines if "WARNING" in line or "WARN" in line]
                    
                    if error_logs:
                        print(f"\n  Found {len(error_logs)} ERROR messages:")
                        for line in error_logs[-5:]:  # Show last 5 errors
                            print(f"  {line}")
                    else:
                        print("  No ERROR messages found")
                        
                    if warning_logs:
                        print(f"\n  Found {len(warning_logs)} WARNING messages:")
                        for line in warning_logs[-5:]:  # Show last 5 warnings
                            print(f"  {line}")
                    else:
                        print("  No WARNING messages found")
                else:
                    print(f"  Container for {service} not found")
            except Exception as e:
                print(f"  Error checking logs: {str(e)}")
            
            print()
        
        input("\nPress enter to continue...")
    
    async def _test_direct_api(self):
        """Test direct API endpoints"""
        self._clear_screen()
        print("\n=== TEST DIRECT API ENDPOINTS ===\n")
        
        if not self.document_id:
            print("No document ID set. Please set a document ID first.")
            input("\nPress enter to continue...")
            return
        
        print("Select API endpoint to test:")
        print("1. Document service - Get document")
        print("2. Document service - Process document chunks")
        print("3. Document service - Force metadata extraction")
        print("4. LLM service - Test metadata extraction")
        print("5. Back to main menu")
        
        choice = input("\nEnter your choice (1-5): ")
        
        if choice == "1":
            # Get document details
            try:
                response = requests.get(f"{self.base_url}/documents/{self.document_id}")
                if response.status_code == 200:
                    print("Document details:")
                    print(json.dumps(response.json(), indent=2))
                else:
                    print(f"Error: {response.status_code} - {response.text}")
            except Exception as e:
                print(f"Error: {str(e)}")
                
        elif choice == "2":
            # Process document chunks
            try:
                response = requests.post(
                    f"{self.base_url}/documents/{self.document_id}/process-chunks",
                    json={"force": True}
                )
                if response.status_code == 200:
                    print("Chunk processing initiated:")
                    print(json.dumps(response.json(), indent=2))
                else:
                    print(f"Error: {response.status_code} - {response.text}")
            except Exception as e:
                print(f"Error: {str(e)}")
                
        elif choice == "3":
            # Force metadata extraction
            try:
                response = requests.post(
                    f"{self.base_url}/documents/{self.document_id}/extract-metadata",
                    json={"force": True}
                )
                if response.status_code == 200:
                    print("Metadata extraction initiated:")
                    print(json.dumps(response.json(), indent=2))
                else:
                    print(f"Error: {response.status_code} - {response.text}")
            except Exception as e:
                print(f"Error: {str(e)}")
                
        elif choice == "4":
            # Test metadata extraction via LLM service
            try:
                # First get document text
                doc_response = requests.get(f"{self.base_url}/documents/{self.document_id}/text")
                if doc_response.status_code == 200:
                    text = doc_response.text
                    # Limit text length for LLM
                    text = text[:5000] + "..." if len(text) > 5000 else text
                    
                    # Send to LLM service directly
                    response = requests.post(
                        f"{self.base_url}/llm/extract-metadata",
                        json={"text": text, "document_id": self.document_id}
                    )
                    
                    if response.status_code == 200:
                        print("LLM Metadata extraction result:")
                        print(json.dumps(response.json(), indent=2))
                    else:
                        print(f"LLM Error: {response.status_code} - {response.text}")
                else:
                    print(f"Error getting document text: {doc_response.status_code} - {doc_response.text}")
            except Exception as e:
                print(f"Error: {str(e)}")
                
        elif choice == "5":
            # Return to main menu
            return
        
        input("\nPress enter to continue...")


async def main():
    tester = ServiceTester()
    await tester.test_menu()


if __name__ == "__main__":
    asyncio.run(main())
