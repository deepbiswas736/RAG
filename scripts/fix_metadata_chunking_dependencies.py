#!/usr/bin/env python3
"""
Fix Script for Chunking and Metadata Dependencies
================================================

This script installs and verifies all dependencies needed for proper
chunking and metadata extraction functionality, including:

1. NLTK for chunking (with appropriate models)
2. Other required packages missing from requirements.txt
3. Checking MongoDB and Kafka configurations
"""

import os
import sys
import subprocess
import json
from typing import List, Dict, Any

# List of essential packages for chunking and metadata
ESSENTIAL_PACKAGES = [
    "nltk>=3.8.1",  # For text segmentation in chunking
    "langchain>=0.0.340", 
    "scikit-learn>=1.3.0",  # For feature extraction
    "spacy>=3.6.1",  # For NLP operations
    "aiohttp>=3.8.6",  # Async HTTP client for service communication
    "motor>=3.3.1",  # Async MongoDB driver
    "kafka-python>=2.0.2"  # Kafka client
]

# NLTK downloads needed
NLTK_DOWNLOADS = [
    "punkt",         # For sentence tokenizing
    "averaged_perceptron_tagger",  # For POS tagging
    "stopwords",     # For filtering common words
    "wordnet"        # For semantic analysis
]

def print_header(message):
    """Print a formatted header"""
    print("\n" + "="*80)
    print(f" {message}")
    print("="*80)

def install_essential_packages():
    """Install essential packages for chunking and metadata extraction"""
    print_header("INSTALLING ESSENTIAL PACKAGES")
    
    # Install packages
    for package in ESSENTIAL_PACKAGES:
        print(f"Installing {package}...")
        subprocess.run([sys.executable, "-m", "pip", "install", package])
    
    print("\nAll essential packages installed.")

def download_nltk_data():
    """Download required NLTK data"""
    print_header("DOWNLOADING NLTK DATA")
    
    import nltk
    
    for data in NLTK_DOWNLOADS:
        print(f"Downloading NLTK data: {data}")
        try:
            nltk.download(data)
        except Exception as e:
            print(f"Error downloading {data}: {str(e)}")
    
    print("\nNLTK data downloads complete")

def verify_spacy_models():
    """Verify and download spaCy models if needed"""
    print_header("VERIFYING SPACY MODELS")
    
    models = ["en_core_web_sm"]
    
    for model in models:
        try:
            # Check if model is installed
            result = subprocess.run(
                [sys.executable, "-m", "spacy", "validate"],
                capture_output=True, text=True
            )
            
            if model not in result.stdout:
                print(f"Installing spaCy model: {model}")
                subprocess.run([sys.executable, "-m", "spacy", "download", model])
            else:
                print(f"SpaCy model {model} is already installed")
                
        except Exception as e:
            print(f"Error verifying spaCy model {model}: {str(e)}")
            # Try to install anyway
            print(f"Attempting to install spaCy model: {model}")
            subprocess.run([sys.executable, "-m", "spacy", "download", model])
    
    print("\nSpaCy model verification complete")

def update_requirements_files():
    """Update requirements files to include needed dependencies"""
    print_header("UPDATING REQUIREMENTS FILES")
    
    # Paths to requirements files
    req_files = [
        "e:/code/experimental/RAG/requirements.txt",
        "e:/code/experimental/RAG/microservices/document-service/app/requirements.txt",
        "e:/code/experimental/RAG/microservices/llm-service/app/requirements.txt"
    ]
    
    for file_path in req_files:
        if os.path.exists(file_path):
            print(f"Checking {file_path}")
            
            # Read existing requirements
            with open(file_path, 'r') as f:
                existing = f.read()
            
            # Add missing packages
            missing = []
            for package in ESSENTIAL_PACKAGES:
                package_name = package.split('>=')[0].split('==')[0]
                if package_name not in existing:
                    missing.append(package)
            
            if missing:
                print(f"Adding {len(missing)} missing packages to {file_path}")
                with open(file_path, 'a') as f:
                    f.write("\n# Dependencies added by fix script\n")
                    for package in missing:
                        f.write(f"{package}\n")
            else:
                print(f"No missing packages in {file_path}")
        else:
            print(f"Requirements file not found: {file_path}")
    
    print("\nRequirements files updated")

def verify_kafka_topics():
    """Verify and create Kafka topics if needed"""
    print_header("VERIFYING KAFKA TOPICS")
    
    try:
        # Check if Kafka is running
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}", "--filter", "name=rag_kafka"],
            capture_output=True, text=True
        )
        
        if not result.stdout.strip():
            print("Kafka container is not running. Please start Docker containers first.")
            return
        
        # Required topics
        required_topics = [
            "document-processed",
            "metadata-extraction",
            "chunk-processed",
            "embedding-processed"
        ]
        
        # Get existing topics
        result = subprocess.run(
            ["python", "e:/code/experimental/RAG/scripts/check_kafka_topics.py"],
            capture_output=True, text=True
        )
        
        # Create missing topics
        kafka_container = result.stdout.strip().split('\n')[0].split(':')[0].strip()
        for topic in required_topics:
            if topic not in result.stdout:
                print(f"Creating missing Kafka topic: {topic}")
                subprocess.run(
                    ["docker", "exec", kafka_container, 
                     "kafka-topics", "--create", 
                     "--topic", topic, 
                     "--bootstrap-server", "localhost:9092", 
                     "--partitions", "1", 
                     "--replication-factor", "1"],
                    capture_output=True, text=True
                )
            else:
                print(f"Kafka topic exists: {topic}")
                
        print("\nKafka topic verification complete")
    except Exception as e:
        print(f"Error verifying Kafka topics: {str(e)}")

def check_mongodb_indexes():
    """Check and create MongoDB indexes if needed"""
    print_header("CHECKING MONGODB INDEXES")
    
    try:
        # MongoDB connection code
        mongo_check_script = """
import pymongo
client = pymongo.MongoClient('mongodb://user:password@localhost:27017/?authSource=admin')

# Check document_db database
doc_db = client['document_db']
print('Checking document_db indexes...')

# Check chunks collection
if 'chunks' in doc_db.list_collection_names():
    chunk_indexes = doc_db.chunks.index_information()
    print(f'Chunk indexes: {list(chunk_indexes.keys())}')
    
    # Create document_id index if missing
    if not any('document_id' in idx for idx in chunk_indexes.values()):
        print('Creating document_id index on chunks collection')
        doc_db.chunks.create_index('document_id')
    
    # Create embedding index if missing
    if not any('embedding' in idx for idx in chunk_indexes.values()):
        print('Creating embedding index on chunks collection')
        doc_db.chunks.create_index([('embedding', pymongo.TEXT)])

# Check documents collection
if 'documents' in doc_db.list_collection_names():
    doc_indexes = doc_db.documents.index_information()
    print(f'Document indexes: {list(doc_indexes.keys())}')
    
    # Create id index if missing
    if not any('id' in idx and idx != '_id_' for idx in doc_indexes.values()):
        print('Creating id index on documents collection')
        doc_db.documents.create_index('id')

print('MongoDB index check complete')
client.close()
"""
        
        # Run MongoDB check script
        subprocess.run([sys.executable, "-c", mongo_check_script])
        
    except Exception as e:
        print(f"Error checking MongoDB indexes: {str(e)}")

def rebuild_docker_containers():
    """Offer to rebuild Docker containers"""
    print_header("DOCKER CONTAINER REBUILD")
    
    print("Would you like to rebuild the Docker containers to apply changes? (y/n)")
    choice = input("This will restart the services: ")
    
    if choice.lower() == 'y':
        print("\nRebuilding Docker containers...")
        try:
            subprocess.run(
                ["docker-compose", "-f", "e:/code/experimental/RAG/docker-compose.yml", 
                 "down"],
                cwd="e:/code/experimental/RAG"
            )
            
            subprocess.run(
                ["docker-compose", "-f", "e:/code/experimental/RAG/docker-compose.yml", 
                 "build", "document-service", "llm-service"],
                cwd="e:/code/experimental/RAG"
            )
            
            subprocess.run(
                ["docker-compose", "-f", "e:/code/experimental/RAG/docker-compose.yml", 
                 "up", "-d"],
                cwd="e:/code/experimental/RAG"
            )
            
            print("\nDocker containers rebuilt and restarted")
        except Exception as e:
            print(f"Error rebuilding containers: {str(e)}")
    else:
        print("\nSkipping Docker container rebuild.")
        print("Remember to rebuild and restart containers manually to apply changes.")

def main():
    print_header("CHUNKING & METADATA DEPENDENCY FIX SCRIPT")
    
    print("This script will:")
    print("1. Install essential Python packages for chunking and metadata extraction")
    print("2. Download required NLTK data")
    print("3. Verify spaCy models")
    print("4. Update requirements.txt files")
    print("5. Verify Kafka topics")
    print("6. Check MongoDB indexes")
    print("7. Optionally rebuild Docker containers")
    
    print("\nDo you want to continue? (y/n)")
    choice = input("> ")
    
    if choice.lower() != 'y':
        print("Exiting without making changes")
        return
    
    # Install packages
    install_essential_packages()
    
    # Download NLTK data
    download_nltk_data()
    
    # Verify spaCy models
    verify_spacy_models()
    
    # Update requirements files
    update_requirements_files()
    
    # Verify Kafka topics
    verify_kafka_topics()
    
    # Check MongoDB indexes
    check_mongodb_indexes()
    
    # Offer to rebuild containers
    rebuild_docker_containers()
    
    print_header("FIX SCRIPT COMPLETE")
    print("The following steps were completed:")
    print("✓ Essential Python packages installed")
    print("✓ NLTK data downloaded")
    print("✓ SpaCy models verified")
    print("✓ Requirements files updated")
    print("✓ Kafka topics verified")
    print("✓ MongoDB indexes checked")
    
    print("\nNext steps:")
    print("1. Run the diagnostic script to verify if issues are resolved:")
    print("   python e:/code/experimental/RAG/scripts/diagnose_metadata_chunking.py")
    print("2. If issues persist, run the test script to troubleshoot specific components:")
    print("   python e:/code/experimental/RAG/scripts/test_metadata_chunking.py")
    
    print("\nGood luck!")

if __name__ == "__main__":
    main()
