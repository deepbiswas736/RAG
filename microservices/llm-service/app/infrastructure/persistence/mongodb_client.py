"""
MongoDB Client Utility
---------------------
Provides MongoDB connection functionality for the LLM service
"""

import os
import logging
import asyncio
from typing import Dict, Any, Optional, List
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import OperationFailure, ServerSelectionTimeoutError, ConnectionFailure

# Configure logging
logger = logging.getLogger(__name__)

class MongoDBClient:
    """MongoDB client utility for LLM service"""
    
    def __init__(self):
        """Initialize the MongoDB client"""
        # Use environment variables with fallbacks for connection settings
        self.mongodb_url = os.getenv('MONGODB_URL', 'mongodb://user:password@mongodb:27017/?authSource=admin&directConnection=true')
        self.db_name = os.getenv('MONGODB_DB_NAME', 'llm_service_db')
        
        self.client = None
        self.db = None
        
        # Collection references
        self.documents = None
        self.chunks = None
        self.metadata = None
        self.topics = None
        
        logger.info(f"MongoDB client initialized with URL: {self.mongodb_url}, DB: {self.db_name}")

    async def initialize(self) -> None:
        """Initialize MongoDB connection and collections"""
        # Retry connection 5 times with increasing timeout
        max_retries = 5
        retry_delay = 2  # seconds
        for attempt in range(max_retries):
            try:
                self.client = AsyncIOMotorClient(self.mongodb_url, serverSelectionTimeoutMS=10000)
                # Check connection is working
                await self.client.admin.command('ismaster')
                self.db = self.client[self.db_name]
                
                # Initialize collections
                self.documents = self.db.documents
                self.chunks = self.db.document_chunks
                self.metadata = self.db.document_metadata
                self.topics = self.db.document_topics
                
                logger.info("Successfully connected to MongoDB")
                await self._ensure_indexes()
                return
            except (ServerSelectionTimeoutError, ConnectionFailure) as e:
                logger.warning(f"Attempt {attempt + 1}/{max_retries}: Could not connect to MongoDB: {e}. Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            except Exception as e:
                logger.error(f"Unexpected error during MongoDB initialization: {e}")
                raise

        logger.error("Failed to connect to MongoDB after multiple retries")
        raise ConnectionError("Failed to connect to MongoDB after multiple retries")

    async def _ensure_indexes(self) -> None:
        """Create necessary indexes for MongoDB collections"""
        try:
            # Document collection indexes
            await self.documents.create_index("document_id", unique=True, sparse=True)
            
            # Document chunks collection indexes
            await self.chunks.create_index("document_id")
            await self.chunks.create_index("chunk_id", unique=True, sparse=True)
            
            # Topics collection indexes
            await self.topics.create_index([("document_id", 1), ("chunk_id", 1)])
            
            logger.info("MongoDB indexes created successfully")
        except Exception as e:
            logger.error(f"Error creating MongoDB indexes: {e}")

    async def get_document_by_id(self, document_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a document by its ID
        
        Args:
            document_id: The document ID
            
        Returns:
            Document data as dictionary or None if not found
        """
        try:
            if not self.documents:
                logger.error("MongoDB client not initialized")
                return None
                
            document = await self.documents.find_one({"document_id": document_id})
            if document:
                logger.info(f"Retrieved document {document_id} from MongoDB")
                return document
            else:
                logger.warning(f"Document {document_id} not found in MongoDB")
                return None
        except Exception as e:
            logger.error(f"Error retrieving document {document_id}: {e}")
            return None

    async def get_document_chunks(self, document_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Retrieve chunks for a document
        
        Args:
            document_id: The document ID
            limit: Optional maximum number of chunks to retrieve
            
        Returns:
            List of document chunks
        """
        try:
            if not self.chunks:
                logger.error("MongoDB client not initialized")
                return []
                
            query = {"document_id": document_id}
            
            # Use find with optional limit
            cursor = self.chunks.find(query)
            if limit:
                cursor = cursor.limit(limit)
                
            chunks = await cursor.to_list(length=1000)  # Cap at 1000 regardless
            logger.info(f"Retrieved {len(chunks)} chunks for document {document_id}")
            return chunks
        except Exception as e:
            logger.error(f"Error retrieving chunks for document {document_id}: {e}")
            return []

    async def update_document_metadata(self, document_id: str, metadata: Dict[str, Any]) -> bool:
        """
        Update a document's metadata
        
        Args:
            document_id: The document ID
            metadata: Updated metadata dictionary
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.documents:
                logger.error("MongoDB client not initialized")
                return False
                
            # Update document metadata using upsert to ensure it exists
            result = await self.documents.update_one(
                {"document_id": document_id},
                {"$set": {"metadata": metadata, "updated_at": asyncio.get_event_loop().time()}},
                upsert=True
            )
            
            if result.modified_count > 0 or result.upserted_id:
                logger.info(f"Updated metadata for document {document_id}")
                return True
            else:
                logger.warning(f"No changes made to metadata for document {document_id}")
                return False
        except Exception as e:
            logger.error(f"Error updating metadata for document {document_id}: {e}")
            return False

    async def update_chunk_metadata(self, chunk_id: str, metadata: Dict[str, Any]) -> bool:
        """
        Update a chunk's metadata
        
        Args:
            chunk_id: The chunk ID
            metadata: Updated metadata dictionary
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.chunks:
                logger.error("MongoDB client not initialized")
                return False
                
            # Update chunk metadata
            result = await self.chunks.update_one(
                {"chunk_id": chunk_id},
                {"$set": {"metadata": metadata, "updated_at": asyncio.get_event_loop().time()}},
                upsert=False  # Don't create new chunks
            )
            
            if result.modified_count > 0:
                logger.info(f"Updated metadata for chunk {chunk_id}")
                return True
            else:
                logger.warning(f"No changes made to metadata for chunk {chunk_id}")
                return False
        except Exception as e:
            logger.error(f"Error updating metadata for chunk {chunk_id}: {e}")
            return False

    async def update_document_and_chunks(
        self, 
        document_id: str, 
        document_metadata: Optional[Dict[str, Any]] = None, 
        chunks_metadata: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """
        Update document and its chunks in a single operation
        
        Args:
            document_id: The document ID
            document_metadata: Updated document metadata
            chunks_metadata: List of dictionaries with chunk_id and metadata
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.documents or not self.chunks:
                logger.error("MongoDB client not initialized")
                return False

            # Update document metadata if provided
            doc_updated = False
            if document_metadata:
                doc_result = await self.documents.update_one(
                    {"document_id": document_id},
                    {"$set": {"metadata": document_metadata, "updated_at": asyncio.get_event_loop().time()}},
                    upsert=True
                )
                doc_updated = (doc_result.modified_count > 0 or doc_result.upserted_id is not None)
            
            # Update chunk metadata if provided
            chunks_updated = 0
            if chunks_metadata:
                for chunk_data in chunks_metadata:
                    chunk_id = chunk_data.get("chunk_id")
                    metadata = chunk_data.get("metadata")
                    
                    if not chunk_id or not metadata:
                        continue
                        
                    result = await self.chunks.update_one(
                        {"chunk_id": chunk_id},
                        {"$set": {"metadata": metadata, "updated_at": asyncio.get_event_loop().time()}},
                        upsert=False
                    )
                    
                    if result.modified_count > 0:
                        chunks_updated += 1
            
            success = doc_updated or chunks_updated > 0
            if success:
                logger.info(f"Updated document {document_id} and {chunks_updated} chunks")
            else:
                logger.warning(f"No updates made to document {document_id} or its chunks")
                
            return success
                
        except Exception as e:
            logger.error(f"Error updating document {document_id} and chunks: {e}")
            return False

    async def save_document_topics(
        self, 
        document_id: str,
        topics: List[str],
        chunk_id: Optional[str] = None
    ) -> bool:
        """
        Save topics for a document or chunk
        
        Args:
            document_id: The document ID
            topics: List of topic strings
            chunk_id: Optional chunk ID if topics are for a specific chunk
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.topics:
                logger.error("MongoDB client not initialized")
                return False
                
            # Create query based on whether chunk_id is provided
            query = {"document_id": document_id}
            if chunk_id:
                query["chunk_id"] = chunk_id
                
            # Update topics using upsert
            result = await self.topics.update_one(
                query,
                {
                    "$set": {
                        "topics": topics,
                        "updated_at": asyncio.get_event_loop().time()
                    }
                },
                upsert=True
            )
            
            success = (result.modified_count > 0 or result.upserted_id is not None)
            if success:
                if chunk_id:
                    logger.info(f"Saved {len(topics)} topics for document {document_id}, chunk {chunk_id}")
                else:
                    logger.info(f"Saved {len(topics)} document-level topics for document {document_id}")
            
            return success
                
        except Exception as e:
            logger.error(f"Error saving topics for document {document_id}: {e}")
            return False

    async def close(self) -> None:
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")
