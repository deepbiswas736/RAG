from typing import List, Optional, Dict
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from datetime import datetime
from pymongo.errors import OperationFailure, ServerSelectionTimeoutError, ConnectionFailure
import json
import asyncio

from ...domain.repositories.document_repository import DocumentRepository
from ...domain.entities.document import Document, Chunk
from ...domain.value_objects.embedding import Embedding
from ...domain.value_objects.metadata import DocumentMetadata

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MongoDBDocumentRepository(DocumentRepository):
    def __init__(self):
        # Get configuration from environment variables with appropriate defaults
        is_docker = os.environ.get('IS_DOCKER', '').lower() == 'true'
        host = "mongodb" if is_docker else "localhost"
        
        # Standard MongoDB connection string (no replica set needed)
        self.mongodb_url = os.getenv('MONGODB_URL', f'mongodb://admin:password@{host}:27017/?authSource=admin')
        self.db_name = os.getenv('MONGODB_DB_NAME', 'rag_db')
        self.vector_index_name = os.getenv('MONGODB_VECTOR_INDEX_NAME', 'vector_index')
        self.vector_dimension = int(os.getenv('VECTOR_DIMENSION', '384'))
        self.vector_metric = os.getenv('VECTOR_METRIC', 'cosine')
        
        self.client = None
        self.db = None
        self.documents = None
        self.chunks = None
        self.vector_search_available = True # Assume available initially, check later
        
        logger.info(f"Initializing MongoDB repository with URL: {self.mongodb_url}, DB: {self.db_name}")

    async def initialize(self):
        """Initialize the repository - should be called at app startup"""
        # Retry connection 5 times with increasing timeout
        max_retries = 5
        retry_delay = 2  # seconds, increased delay
        for attempt in range(max_retries):
            try:
                self.client = AsyncIOMotorClient(self.mongodb_url, serverSelectionTimeoutMS=10000) # Increased timeout
                # The ismaster command is cheap and does not require auth.
                await self.client.admin.command('ismaster')
                self.db = self.client[self.db_name]
                self.documents = self.db.documents
                self.chunks = self.db.chunks
                logger.info("Successfully connected to MongoDB.")
                await self._ensure_indexes()
                # Vector search availability check moved to after index creation
                return
            except (ServerSelectionTimeoutError, ConnectionFailure) as e:
                logger.warning(f"Attempt {attempt + 1}/{max_retries}: Could not connect to MongoDB: {e}. Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2 # Exponential backoff
            except OperationFailure as e:
                logger.error(f"MongoDB operation failed during initialization: {e}")
                # Decide if this is fatal or if we can continue without certain features
                # For example, if index creation fails but connection is okay.
                # Depending on the error, you might set self.vector_search_available = False
                break # Exit retry loop on operational failure after connection
            except Exception as e:
                logger.error(f"An unexpected error occurred during MongoDB initialization: {e}")
                break # Exit retry loop on unexpected error

        logger.error("Failed to connect to MongoDB after multiple retries.")
        # Depending on the application's requirements, you might raise an exception here
        # or allow the application to continue in a degraded state.
        self.vector_search_available = False # Mark DB as unavailable if connection fails

    async def _ensure_indexes(self):
        """Ensure necessary indexes exist, including the vector index."""
        if self.client is None or self.db is None:
            logger.error("Cannot ensure indexes without a valid DB connection.")
            return
        try:
            # Ensure standard indexes first
            await self.documents.create_index([("document_id", 1)], unique=True)
            await self.chunks.create_index([("document_id", 1)])
            await self.chunks.create_index([("chunk_id", 1)], unique=True)
            await self._ensure_vector_index() # Ensure vector index after basic indexes
            logger.info("Successfully ensured standard indexes.")
        except OperationFailure as e:
            logger.error(f"Failed to create standard indexes: {e}")
            # Decide how to handle this - maybe vector search can still work?
        except Exception as e:
            logger.error(f"Error checking/creating indexes: {e}")
            # Handle connection errors if necessary

    async def _ensure_vector_index(self):
        """Check if vector search is available and create the index if needed."""
        try:
            # Check existing indexes for the vector index
            index_info = await self.chunks.index_information()
            if self.vector_index_name in index_info:
                logger.info(f"Vector index '{self.vector_index_name}' already exists.")
                self.vector_search_available = True # Mark as available if index exists
            else:
                logger.info(f"Vector index '{self.vector_index_name}' not found. Attempting creation.")
                # Define the vector index structure
                vector_index_command = {
                    "createIndexes": "chunks",
                    "indexes": [{ # Corrected field name
                        "name": self.vector_index_name,
                        "key": {
                            "embedding.vector": "cosmosDbVectorSearch" # Use "cosmosDbVectorSearch" for Azure Cosmos DB for MongoDB vCore
                        },
                        "cosmosDbVectorSearchOptions": {
                            "type": "vector-ivf",
                            "dimensions": self.vector_dimension,
                            "similarity": self.vector_metric,
                            "numLists": 1 # Adjust based on expected data size
                        }
                    }]
                }
                
                logger.info(f"Attempting to create vector index '{self.vector_index_name}'...")
                await self.db.command(vector_index_command) # Use db.command
                logger.info(f"Successfully created vector index '{self.vector_index_name}'.")
                self.vector_search_available = True

        except OperationFailure as e:
            # Specific error code for index already exists (though the check above should prevent this)
            # Error code 11000 is duplicate key, 85 is IndexOptionsConflict, 68 is IndexAlreadyExists
            if e.code in [11000, 85, 68]:
                 logger.info(f"Vector index '{self.vector_index_name}' already exists (caught by exception).")
                 self.vector_search_available = True
            else:
                # Check if the error indicates vector search is not supported
                if "vector search" in str(e).lower() or "CosmosDbVectorSearch" in str(e):
                    logger.warning(f"Vector search might not be supported by the MongoDB instance: {e}")
                    self.vector_search_available = False # Mark as unavailable
                else:
                    logger.error(f"Failed to create vector index '{self.vector_index_name}': {e}")
                    self.vector_search_available = False # Mark as unavailable
        except Exception as e:
            logger.error(f"An unexpected error occurred during vector index check/creation: {e}")
            self.vector_search_available = False

    async def save(self, document: Document) -> str:
        doc_dict = {
            "title": document.title,
            "content": document.content,
            "metadata": document.metadata.__dict__,
            "created_at": document.created_at,
            "updated_at": document.updated_at
        }
        result = await self.documents.insert_one(doc_dict)
        return str(result.inserted_id)

    async def save_chunks(self, chunks: List[Chunk]) -> List[str]:
        chunk_dicts = [
            {
                "content": chunk.content,
                "embedding": {
                    "vector": chunk.embedding.vector,
                    "dimension": chunk.embedding.dimension
                },
                "metadata": chunk.metadata.__dict__,
                "source": chunk.source
            }
            for chunk in chunks
        ]
        result = await self.chunks.insert_many(chunk_dicts)
        return [str(id) for id in result.inserted_ids]

    async def search_similar(self, embedding: Embedding, limit: int = 5) -> List[Chunk]:
        # Use vector search if available
        if self.vector_search_available:
            chunks = await self._search_vector(embedding, limit)
            if chunks:
                return chunks
        
        # Fall back to text search as a last resort
        return await self._search_text_fallback(embedding, limit)

    async def _search_vector(self, embedding: Embedding, limit: int) -> List[Chunk]:
        """Search using MongoDB 7.0+ vector search"""
        try:
            # Using MongoDB 7.0+ $vectorSearch operator
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": self.vector_index_name,
                        "path": "embedding.vector",
                        "queryVector": embedding.vector,
                        "numCandidates": limit * 3,
                        "limit": limit
                    }
                },
                {
                    "$project": {
                        "content": 1,
                        "metadata": 1,
                        "source": 1,
                        "embedding": 1,
                        "score": { "$meta": "vectorSearchScore" }
                    }
                }
            ]
            
            logger.info(f"Executing vector search with {len(embedding.vector)} dimensions")
            cursor = self.chunks.aggregate(pipeline)
            results = await cursor.to_list(length=limit)
            
            chunks = []
            for doc in results:
                chunks.append(Chunk(
                    id=str(doc["_id"]),
                    content=doc["content"],
                    embedding=Embedding.create(doc["embedding"]["vector"]),
                    metadata=DocumentMetadata.from_dict(doc["metadata"]),
                    source=doc["source"]
                ))
            
            if chunks:
                logger.info(f"Vector search found {len(chunks)} results")
                return chunks
            else:
                logger.warning("Vector search returned no results")
                return []
                
        except Exception as e:
            logger.warning(f"Error during vector search: {e}")
            return []

    async def _search_text_fallback(self, embedding: Embedding, limit: int) -> List[Chunk]:
        """Fall back to text search when vector search isn't available"""
        logger.info("Falling back to text search")
        chunks = []
        
        # Use the first few values from the embedding vector to create a search query
        # This is a simplistic approach but better than nothing
        query_terms = []
        for i, val in enumerate(embedding.vector[:5]):
            term = f"v{i}_{round(val * 100)}"
            query_terms.append(term)
            
        query_text = " ".join(query_terms)
        
        try:
            # First try content-based search for more relevant results
            cursor = self.chunks.find(
                {"$text": {"$search": query_text}},
                {"score": {"$meta": "textScore"}}
            ).sort([("score", {"$meta": "textScore"})]).limit(limit)
            
            async for doc in cursor:
                chunks.append(Chunk(
                    id=str(doc["_id"]),
                    content=doc["content"],
                    embedding=Embedding.create(doc["embedding"]["vector"]),
                    metadata=DocumentMetadata.from_dict(doc["metadata"]),
                    source=doc["source"]
                ))
                
            if not chunks:
                # If that fails, try the most recent documents as a last resort
                logger.info("Text search yielded no results, retrieving most recent chunks")
                cursor = self.chunks.find().sort("_id", -1).limit(limit)
                async for doc in cursor:
                    chunks.append(Chunk(
                        id=str(doc["_id"]),
                        content=doc["content"],
                        embedding=Embedding.create(doc["embedding"]["vector"]),
                        metadata=DocumentMetadata.from_dict(doc["metadata"]),
                        source=doc["source"]
                    ))
        except Exception as e:
            logger.error(f"Error during fallback search: {e}")
            
        return chunks

    async def find_by_id(self, document_id: str) -> Optional[Document]:
        doc = await self.documents.find_one({"_id": document_id})
        if not doc:
            return None
        
        chunks = await self.find_chunks_by_document_id(document_id)
        return Document(
            id=str(doc["_id"]),
            title=doc["title"],
            content=doc["content"],
            chunks=chunks,
            metadata=DocumentMetadata.from_dict(doc["metadata"]),
            created_at=doc["created_at"],
            updated_at=doc["updated_at"]
        )

    async def find_chunks_by_document_id(self, document_id: str) -> List[Chunk]:
        cursor = self.chunks.find({"metadata.document_id": document_id})
        chunks = []
        async for doc in cursor:
            chunks.append(Chunk(
                id=str(doc["_id"]),
                content=doc["content"],
                embedding=Embedding.create(doc["embedding"]["vector"]),
                metadata=DocumentMetadata.from_dict(doc["metadata"]),
                source=doc["source"]
            ))
        return chunks

    async def check_vector_index_status(self):
        """Diagnostic function to check vector index status"""
        try:
            # Get collection stats to see if vector indexes exist
            collection_stats = await self.db.command("collStats", "chunks")
            
            # Get index details
            indexes = await self.chunks.index_information()
            
            # Check for vector index
            index_found = self.vector_index_name in indexes
            vector_search_enabled = self.vector_search_available
            
            # Check MongoDB version
            server_info = await self.client.server_info()
            mongodb_version = server_info.get('version', 'Unknown')
            
            # Check if any documents with embeddings exist
            sample_doc = await self.chunks.find_one({"embedding.vector": {"$exists": True}})
            has_embeddings = sample_doc is not None
            
            if has_embeddings and sample_doc.get('embedding') and 'vector' in sample_doc['embedding']:
                embedding_sample = sample_doc['embedding']['vector']
                embedding_dimension = len(embedding_sample)
                expected_dimension = self.vector_dimension
                dimension_match = embedding_dimension == expected_dimension
            else:
                embedding_sample = None
                embedding_dimension = None
                dimension_match = False
                
            # Collect results
            status = {
                "mongodb_version": mongodb_version,
                "vector_search_enabled": vector_search_enabled,
                "vector_index_found": index_found,
                "index_name": self.vector_index_name,
                "has_documents_with_embeddings": has_embeddings,
                "embedding_dimension": embedding_dimension,
                "expected_dimension": self.vector_dimension,
                "dimension_match": dimension_match
            }
            
            return status
            
        except Exception as e:
            logger.error(f"Error checking vector index status: {e}")
            return {
                "error": str(e),
                "vector_search_available": self.vector_search_available
            }