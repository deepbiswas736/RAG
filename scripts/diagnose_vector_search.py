#!/usr/bin/env python
import asyncio
import os
import logging
from motor.motor_asyncio import AsyncIOMotorClient
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def diagnose_vector_search():
    # Connection settings - using the same ones from your app
    mongodb_url = os.getenv('MONGODB_URL', 'mongodb://user:password@localhost:27017/?authSource=admin&directConnection=true')
    db_name = "test_vector_db"
    vector_dimension = 384
    
    logger.info(f"Connecting to MongoDB at {mongodb_url}")
    client = AsyncIOMotorClient(mongodb_url)
    db = client[db_name]
    
    # 1. Check MongoDB version and capabilities
    try:
        server_info = await client.admin.command('buildInfo')
        logger.info(f"MongoDB version: {server_info.get('version')}")
        
        # Check if this is Atlas or has Atlas features
        try:
            cmd_line_opts = await client.admin.command('getCmdLineOpts')
            is_atlas = "atlas" in str(cmd_line_opts).lower()
            logger.info(f"Is Atlas or Atlas-like: {is_atlas}")
        except Exception as e:
            logger.info(f"Could not determine if Atlas: {e}")
    except Exception as e:
        logger.error(f"Error getting server info: {e}")
    
    # 2. Create test collection with vectors
    collection_name = "vector_test"
    collection = db[collection_name]
    
    # Drop if exists
    await collection.drop()
    logger.info(f"Created fresh collection: {collection_name}")
    
    # Create test documents with embeddings
    docs = []
    for i in range(5):
        vector = np.random.rand(vector_dimension).tolist()
        docs.append({
            "text": f"Test document {i+1}",
            "embedding": {
                "vector": vector,
                "dimension": vector_dimension
            }
        })
    
    await collection.insert_many(docs)
    logger.info(f"Inserted {len(docs)} test documents with vector embeddings")
    
    # 3. Try Atlas Search Index creation methods
    try:
        # Method 1: Try using createSearchIndex command (Atlas standard)
        index_def1 = {
            "name": "vector_index_1",
            "definition": {
                "mappings": {
                    "dynamic": False,
                    "fields": {
                        "embedding": {
                            "type": "document",
                            "fields": {
                                "vector": {
                                    "type": "knnVector",
                                    "dimensions": vector_dimension,
                                    "similarity": "cosine"
                                }
                            }
                        }
                    }
                }
            }
        }
        
        try:
            await collection.create_search_index(index_def1)
            logger.info("Successfully initiated Atlas Search index creation using collection.create_search_index()")
            await asyncio.sleep(15)  # Wait for index to build
        except Exception as e:
            logger.error(f"Error with collection.create_search_index(): {e}")
            
        # Method 2: Try using $createSearchIndexes command
        try:
            index_def2 = {
                "createSearchIndexes": collection_name,
                "indexes": [{
                    "name": "vector_index_2",
                    "definition": {
                        "mappings": {
                            "dynamic": False,
                            "fields": {
                                "embedding.vector": {
                                    "type": "knnVector",
                                    "dimensions": vector_dimension,
                                    "similarity": "cosine"
                                }
                            }
                        }
                    }
                }]
            }
            await db.command(index_def2)
            logger.info("Successfully initiated Atlas Search index creation using db.command()")
            await asyncio.sleep(15)  # Wait for index to build
        except Exception as e:
            logger.error(f"Error with db.command() for search index: {e}")
            
        # Method 3: Try native MongoDB vector index
        try:
            native_index_cmd = {
                "createIndexes": collection_name,
                "indexes": [{
                    "name": "vector_index_native",
                    "key": { "embedding.vector": "vector" },
                    "vectorOptions": {
                        "type": "ivfFlat",
                        "dimensions": vector_dimension,
                        "similarity": "cosine"
                    }
                }]
            }
            await db.command(native_index_cmd)
            logger.info("Successfully created native vector index")
        except Exception as e:
            logger.error(f"Error creating native vector index: {e}")
            
        # 4. List indexes to see what was created
        try:
            search_indexes = await collection.list_search_indexes()
            logger.info(f"Search indexes found: {search_indexes}")
        except Exception as e:
            logger.error(f"Error listing search indexes: {e}")
            
        indexes = await collection.index_information()
        logger.info(f"Standard indexes found: {indexes}")
            
        # 5. Try different vector search syntaxes
        test_vector = np.random.rand(vector_dimension).tolist()
        
        # Try Atlas Search with knnVector
        try:
            pipeline1 = [
                {
                    "$search": {
                        "index": "vector_index_1",
                        "knnVector": {
                            "vector": test_vector,
                            "path": "embedding.vector",
                            "k": 3
                        }
                    }
                }
            ]
            cursor1 = collection.aggregate(pipeline1)
            results1 = await cursor1.to_list(length=10)
            logger.info(f"Atlas Search knnVector results count: {len(results1)}")
        except Exception as e:
            logger.error(f"Error with Atlas Search knnVector query: {e}")
            
        # Try Atlas Search with knnBeta
        try:
            pipeline2 = [
                {
                    "$search": {
                        "index": "vector_index_1",
                        "knnBeta": {
                            "vector": test_vector,
                            "path": "embedding.vector",
                            "k": 3
                        }
                    }
                }
            ]
            cursor2 = collection.aggregate(pipeline2)
            results2 = await cursor2.to_list(length=10)
            logger.info(f"Atlas Search knnBeta results count: {len(results2)}")
        except Exception as e:
            logger.error(f"Error with Atlas Search knnBeta query: {e}")
            
        # Try native $vectorSearch
        try:
            pipeline3 = [
                {
                    "$vectorSearch": {
                        "index": "vector_index_native",
                        "path": "embedding.vector",
                        "queryVector": test_vector,
                        "numCandidates": 10,
                        "limit": 3
                    }
                }
            ]
            cursor3 = collection.aggregate(pipeline3)
            results3 = await cursor3.to_list(length=10)
            logger.info(f"Native $vectorSearch results count: {len(results3)}")
        except Exception as e:
            logger.error(f"Error with native $vectorSearch query: {e}")
        
    except Exception as e:
        logger.error(f"Error during vector index testing: {e}")
    
    logger.info("Vector search diagnosis complete")

if __name__ == "__main__":
    asyncio.run(diagnose_vector_search())