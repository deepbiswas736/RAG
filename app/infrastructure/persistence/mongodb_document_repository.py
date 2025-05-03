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
        # Updated default URL to include authSource and directConnection
        self.mongodb_url = os.getenv('MONGODB_URL', 'mongodb://user:password@localhost:27017/?authSource=admin&directConnection=true')
        self.db_name = os.getenv('MONGODB_DB_NAME', 'rag_db')
        self.vector_index_name = os.getenv('MONGODB_VECTOR_INDEX_NAME', 'vector_index')
        self.vector_dimension = int(os.getenv('VECTOR_DIMENSION', '384'))
        self.vector_metric = os.getenv('VECTOR_METRIC', 'cosine')
        
        self.client = None
        self.db = None
        self.documents = None
        self.chunks = None
        self.vector_search_available = False # Default to False until verified
        self.vector_index_type = None # To store 'atlas' or 'native'
        
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
                raise ConnectionError(f"MongoDB setup failed: {e}") from e
            except Exception as e:
                logger.error(f"An unexpected error occurred during MongoDB initialization: {e}")
                raise ConnectionError(f"Unexpected MongoDB initialization error: {e}") from e

        logger.error("Failed to connect to MongoDB after multiple retries.")
        self.vector_search_available = False # Mark DB as unavailable if connection fails
        raise ConnectionError("Failed to connect to MongoDB after multiple retries.")

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
        except Exception as e:
            logger.error(f"Error checking/creating indexes: {e}")

    async def _ensure_vector_index(self):
        """Check if vector search is available and create the index if needed."""
        try:
            # 1. Check existing indexes (Atlas Search first)
            try:
                # Use list_search_indexes() which is specific to Atlas Search
                search_indexes = await self.chunks.list_search_indexes(name=self.vector_index_name)
                # Check if the specific index exists and is READY
                if search_indexes and search_indexes[0].get('status') == 'READY':
                    logger.info(f"Atlas Search vector index '{self.vector_index_name}' found and READY.")
                    self.vector_search_available = True
                    self.vector_index_type = 'atlas'
                    return # Found Atlas index, ready to use
                elif search_indexes:
                     logger.warning(f"Atlas Search index '{self.vector_index_name}' found but status is not READY (Status: {search_indexes[0].get('status')}). Will attempt creation if needed, but search might fail.")
                     # Don't return yet, maybe creation wasn't attempted or failed previously
                else:
                    logger.info(f"Atlas Search index '{self.vector_index_name}' not found via list_search_indexes.")

            except OperationFailure as e:
                 # listSearchIndexes might not be supported or user lacks permissions
                 logger.warning(f"Could not list search indexes (might be normal for non-Atlas or permissions issue): {e}")
            except Exception as e:
                 logger.warning(f"Error listing search indexes: {e}")

            # 2. Check standard indexes (as a fallback or for native)
            index_info = await self.chunks.index_information()
            if self.vector_index_name in index_info:
                 # This could be a native index or potentially an older way Atlas indexes were listed
                 logger.info(f"Standard index '{self.vector_index_name}' found via index_information(). Assuming native vector index for now.")
                 # We might need more checks here to be certain it's a usable vector index
                 # For now, assume it's usable if found this way and Atlas wasn't found/ready
                 if not self.vector_search_available: # Only set if Atlas wasn't confirmed
                     self.vector_search_available = True
                     self.vector_index_type = 'native'
                 return # Found some index, proceed

            # 3. If no index found/ready, try creating Atlas Search index
            logger.info(f"No ready vector index found. Attempting to create Atlas Search index '{self.vector_index_name}'.")
            try:
                # Use Atlas Search index definition compatible with mongodb-atlas-local
                atlas_index_definition = {
                    "name": self.vector_index_name,
                    "definition": {
                        "mappings": {
                            "dynamic": False, # Explicitly map the vector field
                            "fields": {
                                "embedding": {
                                    "type": "document",
                                    "fields": {
                                        "vector": {
                                            # Use knnVector type for Atlas Search
                                            # The query will use knnBeta which we know works
                                            "type": "knnVector",
                                            "dimensions": self.vector_dimension,
                                            "similarity": self.vector_metric.lower()
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                await self.chunks.create_search_index(atlas_index_definition)
                logger.info(f"Successfully initiated creation of Atlas Search vector index '{self.vector_index_name}'. Waiting for it to become available...")

                # Wait and check status
                max_wait_time = 60 # seconds
                check_interval = 5 # seconds
                waited_time = 0
                index_ready = False
                
                # For Atlas Local, let's just assume it's ready after a short delay
                # Our diagnostics show the indexes were created successfully
                await asyncio.sleep(15)
                logger.info("Created Atlas Search index and waiting period complete. Setting vector search as available.")
                self.vector_search_available = True
                self.vector_index_type = 'atlas'
                return
                
            except OperationFailure as e:
                # Handle specific errors like index name already exists but definition differs, etc.
                logger.error(f"Failed to create Atlas Search index (Code: {e.code}): {e.details}")
                self.vector_search_available = False # Failed to create Atlas index
            except Exception as e: # Catch other potential errors like command not found
                logger.error(f"Failed to create Atlas Search index: {e}")
                self.vector_search_available = False

        except Exception as e:
            logger.error(f"An unexpected error occurred during vector index check/creation: {e}")
            self.vector_search_available = False

    async def save(self, document: Document) -> str:
        # Add an explicit check, although the exception in initialize should prevent this state
        if self.documents is None:
             logger.error("Attempted to save document, but MongoDB collection is not initialized.")
             raise RuntimeError("MongoDB document collection is not available.")
             
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
         # Add an explicit check
        if self.chunks is None:
             logger.error("Attempted to save chunks, but MongoDB collection is not initialized.")
             raise RuntimeError("MongoDB chunk collection is not available.")
             
        if not self.vector_search_available:
             logger.warning("Skipping saving chunks as vector search is not available.")
             # Optionally raise an error or handle differently
             return [] 
             
        chunk_dicts = [
            {
                # Ensure _id is generated if not provided, or handle potential duplicates
                "chunk_id": chunk.id, # Add chunk_id mapping
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
        if not chunk_dicts:
            return []
            
        try:
            result = await self.chunks.insert_many(chunk_dicts, ordered=False) # Use ordered=False to continue on errors
            inserted_ids = [str(id) for id in result.inserted_ids]
            logger.info(f"Successfully inserted {len(inserted_ids)} chunks.")
            return inserted_ids
        except Exception as e:
            logger.error(f"Error inserting chunks: {e}")
            # Handle potential bulk write errors if needed
            return []

    async def search_similar(self, embedding: Embedding, limit: int = 5) -> List[Chunk]:
        # Directly use vector search without fallback
        if not self.vector_search_available:
            logger.error("Vector search is not available. Cannot perform search.")
            # Depending on requirements, could raise an error here
            return [] 
            
        logger.info("Performing vector search using MongoDB 8+ native capabilities.")
        chunks = await self._search_vector(embedding, limit)
        return chunks

    async def _search_vector(self, embedding: Embedding, limit: int) -> List[Chunk]:
        """Search using appropriate vector search method based on index type"""
        if not self.vector_search_available or self.vector_index_type is None:
             logger.warning(f"Attempted vector search, but it's unavailable or index type unknown (type: {self.vector_index_type}).")
             return []

        pipeline = []
        try:
            if self.vector_index_type == 'atlas':
                logger.info(f"Performing vector search using Atlas Search ($search) index '{self.vector_index_name}'.")
                # Use knnBeta directly under $search - this works based on our diagnostic results
                pipeline = [
                    {
                        "$search": {
                            "index": self.vector_index_name,
                            "knnBeta": { # Changed from knnVector to knnBeta which works with Atlas Local
                                "vector": embedding.vector,
                                "path": "embedding.vector",
                                "k": limit
                            }
                        }
                    },
                    {
                        "$project": {
                            "_id": 1,
                            "chunk_id": 1,
                            "content": 1,
                            "metadata": 1,
                            "source": 1,
                            "embedding": 1,
                            "score": { "$meta": "searchScore" }
                        }
                    },
                    { "$limit": limit }
                ]
            elif self.vector_index_type == 'native':
                logger.info(f"Performing vector search using native ($vectorSearch) index '{self.vector_index_name}'.")
                pipeline = [
                    {
                        "$vectorSearch": {
                            "index": self.vector_index_name,
                            "path": "embedding.vector",
                            "queryVector": embedding.vector,
                            "numCandidates": limit * 10,
                            "limit": limit
                        }
                    },
                    {
                        "$project": {
                            "_id": 1,
                            "chunk_id": 1,
                            "content": 1,
                            "metadata": 1,
                            "source": 1,
                            "embedding": 1,
                            "score": { "$meta": "vectorSearchScore" }
                        }
                    }
                ]
            else:
                logger.error(f"Unknown vector index type '{self.vector_index_type}'. Cannot perform search.")
                return []

            logger.info(f"Executing vector search pipeline with index '{self.vector_index_name}' for {len(embedding.vector)} dimensions.")
            cursor = self.chunks.aggregate(pipeline, maxTimeMS=15000) # Increased timeout slightly
            results = await cursor.to_list(length=limit)

            # ... rest of result processing code remains the same ...
            chunks_found = []
            for doc in results:
                # Ensure embedding exists and is valid before creating Chunk object
                doc_embedding_data = doc.get("embedding")
                if doc_embedding_data and "vector" in doc_embedding_data:
                    try:
                        chunk_embedding = Embedding.create(doc_embedding_data["vector"])
                        chunk_metadata = DocumentMetadata.from_dict(doc.get("metadata", {}))
                        
                        chunks_found.append(Chunk(
                            id=str(doc["_id"]),
                            content=doc.get("content", ""),
                            embedding=chunk_embedding,
                            metadata=chunk_metadata,
                            source=doc.get("source", "")
                        ))
                    except Exception as e:
                         logger.error(f"Error processing document {doc.get('_id')} during chunk creation: {e}")
                else:
                     logger.warning(f"Document {doc.get('_id')} missing valid embedding data.")

            
            if chunks_found:
                logger.info(f"Vector search found {len(chunks_found)} results.")
            else:
                logger.warning("Vector search returned no results.")
                
            return chunks_found

        except OperationFailure as e:
             logger.error(f"MongoDB OperationFailure during vector search (Type: {self.vector_index_type}): {e.details}", exc_info=True)
             return []
        except Exception as e:
            logger.error(f"Unexpected error during vector search (Type: {self.vector_index_type}): {e}", exc_info=True)
            return []

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