#!/usr/bin/env python
"""
Test script to verify that MongoDB Atlas Vector Search is working correctly.
This script will:
1. Connect to the MongoDB instance
2. Create a test collection with vector data
3. Set up a vector search index
4. Perform a sample vector search
"""

import asyncio
import os
import logging
from motor.motor_asyncio import AsyncIOMotorClient
import numpy as np
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_vector_search():
    # Get MongoDB connection details from environment
    # Updated default URL to include authSource and directConnection
    mongodb_url = os.getenv('MONGODB_URL', 'mongodb://user:password@localhost:27017/?authSource=admin&directConnection=true')
    db_name = os.getenv('MONGODB_DB_NAME', 'rag_db')
    vector_dimension = int(os.getenv('VECTOR_DIMENSION', '384'))
    
    logger.info(f"Connecting to MongoDB at {mongodb_url}")
    
    # Initialize MongoDB client
    client = AsyncIOMotorClient(mongodb_url, serverSelectionTimeoutMS=5000)
    db = client[db_name]
    
    # Create test collection
    test_collection = db.vector_test_collection
    
    # Check if we're connected to MongoDB Atlas (cloud or local)
    try:
        info = await client.admin.command('buildInfo')
        logger.info(f"Connected to MongoDB version: {info.get('version')}")
        
        # Check if Atlas features are available
        is_atlas = 'mongodb+srv' in mongodb_url
        try:
            result = await client.admin.command('getParameter', '*')
            logger.info("Testing for Atlas features...")
            is_atlas = is_atlas or 'featureCompatibilityVersion' in result
        except Exception as e:
            logger.debug(f"Error checking if Atlas instance: {e}")
        
        if is_atlas:
            logger.info("MongoDB Atlas features detected!")
        else:
            logger.info("Connected to standard MongoDB (non-Atlas)")
            
    except Exception as e:
        logger.error(f"Error checking MongoDB version: {e}")
    
    # Clean up any existing test data
    await test_collection.drop()
    logger.info("Dropped existing test collection")
    
    # Create test documents with vector embeddings
    test_docs = []
    for i in range(10):
        # Create random vector for testing
        vector = np.random.rand(vector_dimension).tolist()
        
        test_docs.append({
            "content": f"Test document {i+1}",
            "embedding": {
                "vector": vector,
                "dimension": vector_dimension
            },
            "metadata": {
                "test_id": i+1
            }
        })
    
    # Insert test documents
    await test_collection.insert_many(test_docs)
    logger.info(f"Inserted {len(test_docs)} test documents with vector embeddings")
    
    # Try to set up vector search index
    try:
        # First create a standard text index
        await test_collection.create_index([("content", "text")], name="content_text_index")
        logger.info("Created text search index")
        
        # Try to create vector index using Atlas approach
        try:
            index_definition = {
                "mappings": {
                    "dynamic": True,
                    "fields": {
                        "embedding.vector": {
                            "dimensions": vector_dimension,
                            "similarity": "cosine",
                            "type": "knnVector"
                        }
                    }
                }
            }
            
            # Create the search index
            await db.command({
                "createSearchIndex": "vector_test_collection",
                "definition": index_definition
            })
            
            logger.info("Successfully created Atlas Vector Search index")
            vector_search_available = True
            
        except Exception as e:
            logger.warning(f"Could not create Atlas Vector Search index: {e}")
            logger.warning("Trying standard vector index...")
            
            # Try standard MongoDB vector index as fallback
            try:
                await test_collection.create_index(
                    [("embedding.vector", "hashed")],
                    name="vector_hashed_index"
                )
                logger.info("Created standard hashed index for vectors")
                vector_search_available = False
            except Exception as e:
                logger.error(f"Failed to create any vector index: {e}")
                vector_search_available = False
    
    except Exception as e:
        logger.error(f"Error creating indexes: {e}")
        vector_search_available = False
    
    # Test vector search if available
    if vector_search_available:
        try:
            # Generate a test vector query
            query_vector = np.random.rand(vector_dimension).tolist()
            
            # Try Atlas vector search
            pipeline = [
                {
                    "$search": {
                        "index": "vector_test_collection",  # Adjust index name if needed
                        "knnBeta": {
                            "vector": query_vector,
                            "path": "embedding.vector",
                            "k": 3
                        }
                    }
                },
                {
                    "$project": {
                        "content": 1,
                        "metadata": 1,
                        "score": {"$meta": "searchScore"}
                    }
                }
            ]
            
            logger.info("Executing vector search...")
            cursor = test_collection.aggregate(pipeline)
            results = await cursor.to_list(length=3)
            
            if results:
                logger.info(f"Vector search successful! Found {len(results)} matching documents")
                for i, doc in enumerate(results):
                    logger.info(f"Result {i+1}: {doc['content']} (score: {doc.get('score', 'N/A')})")
            else:
                logger.warning("Vector search returned no results")
        
        except Exception as e:
            logger.error(f"Error performing vector search: {e}")
    else:
        logger.warning("Vector search not available, skipping search test")
    
    logger.info("Test completed")

if __name__ == "__main__":
    asyncio.run(test_vector_search())