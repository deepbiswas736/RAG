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
from bson import ObjectId

# Configure logging
logger = logging.getLogger(__name__)

class MongoDBClient:
    """MongoDB client utility for LLM service"""
    
    def __init__(self, connection_string: Optional[str] = None, db_name: Optional[str] = None):
        """Initialize the MongoDB client"""
        # Prioritize MONGO_URI, then MONGODB_URL, then the default
        self.connection_string = os.getenv("MONGO_URI") or \
                                 os.getenv("MONGODB_URL") or \
                                 connection_string or \
                                 "mongodb://user:password@mongodb:27017/?authSource=admin&replicaSet=rs0&retryWrites=true"
        
        self.db_name = db_name or os.getenv("MONGODB_DB_NAME", "rag_db")
        logger.info(f"Attempting to connect to MongoDB with connection string: {self.connection_string}")
        
        self.client = None
        self.db = None
        # Collection references
        self.documents = None
        self.chunks = None
        
        logger.info(f"MongoDB client initialized with database: {self.db_name}")
        
    async def initialize(self) -> None:
        """Initialize MongoDB connection and collections"""
        # Connect to MongoDB with replica set awareness and improved connection parameters
        connect_kwargs = {
            "serverSelectionTimeoutMS": 5000,  # 5 seconds timeout for server selection
            "connectTimeoutMS": 10000,         # 10 seconds connection timeout
            "socketTimeoutMS": 30000,          # 30 seconds socket timeout
            "retryWrites": True,               # Enable retry for write operations
        }
        
        # Retry connection 5 times with increasing timeout
        max_retries = 5
        retry_delay = 2  # seconds
        for attempt in range(max_retries):
            try:
                self.client = AsyncIOMotorClient(self.connection_string, **connect_kwargs)
                # Check connection is working
                await self.client.admin.command('ping')
                self.db = self.client[self.db_name]
                
                # Initialize collections
                self.documents = self.db.documents
                self.chunks = self.db.document_chunks
                
                logger.info(f"Successfully connected to MongoDB database: {self.db_name}")
                await self._ensure_indexes()
                return
            except (ServerSelectionTimeoutError, ConnectionFailure) as e:
                logger.warning(f"Attempt {attempt + 1}/{max_retries}: Could not connect to MongoDB: {e}. Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            except Exception as e:
                logger.error(f"Unexpected error during MongoDB initialization: {e}")
                raise        logger.error("Failed to connect to MongoDB after multiple retries")
        raise ConnectionError("Failed to connect to MongoDB after multiple retries")
        
    async def _ensure_indexes(self) -> None:
        """Create necessary indexes for MongoDB collections"""
        try:
            # Document collection indexes
            await self.documents.create_index("document_id", unique=True, sparse=True)
            await self.documents.create_index("metadata.topics")  # Add index for topics in metadata
              # Document chunks collection indexes
            await self.chunks.create_index("document_id")
            await self.chunks.create_index("id", unique=True, sparse=True)  # UUID string identifier
            await self.chunks.create_index("metadata.topics")  # Add index for topics in metadata
            
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
            if self.documents is None:
                logger.error("MongoDB client not initialized")
                return None

            # Convert string ID to ObjectId if valid format
            doc_id = document_id
            if ObjectId.is_valid(document_id):
                doc_id = ObjectId(document_id)

            # Try to find by both ObjectId and string ID
            query = {"$or": [{"_id": doc_id}, {"document_id": document_id}]}
            document = await self.documents.find_one(query)
            
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
            if self.chunks is None:
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
            if self.documents is None:
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
            if self.chunks is None:
                logger.error("MongoDB client not initialized")
                return False
            
            # Convert string ID to ObjectId if valid format
            chunk_obj_id = chunk_id
            if ObjectId.is_valid(chunk_id):
                chunk_obj_id = ObjectId(chunk_id)
            
            # Update chunk metadata - try both id and _id fields
            result = await self.chunks.update_one(
                {"$or": [{"id": chunk_id}, {"_id": chunk_obj_id}]},
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
            if self.documents is None or self.chunks is None:
                logger.error("MongoDB client not initialized")
                return False

            # Convert document ID to ObjectId if valid format
            doc_id = document_id
            if ObjectId.is_valid(document_id):
                doc_id = ObjectId(document_id)

            # Update document metadata if provided
            doc_updated = False
            if document_metadata:
                doc_result = await self.documents.update_one(
                    {"_id": doc_id},
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
                    
                    # Convert chunk ID to ObjectId if valid format
                    chunk_obj_id = chunk_id
                    if ObjectId.is_valid(chunk_id):
                        chunk_obj_id = ObjectId(chunk_id)
                        
                    result = await self.chunks.update_one(
                        {"$or": [{"id": chunk_id}, {"_id": chunk_obj_id}]},
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
        Save topics for a document chunk by updating the metadata field in chunks collection
        
        Args:
            document_id: The document ID
            topics: List of topic strings
            chunk_id: Optional chunk ID if topics are for a specific chunk
            
        Returns:
            True if successful, False otherwise
        """       
        try:
            if self.chunks is None:
                logger.error("MongoDB client not initialized")
                return False
            
            # Always use the chunks collection
            collection = self.chunks
            
            if chunk_id:
                # Convert chunk ID to ObjectId if valid format
                chunk_obj_id = chunk_id
                if ObjectId.is_valid(chunk_id):
                    chunk_obj_id = ObjectId(chunk_id)
                    
                # Query using both id field or _id for compatibility
                query = {"$or": [{"id": chunk_id}, {"_id": chunk_obj_id}]}
            else:
                query = {"document_id": document_id}
            
            # Update topics in the metadata field
            result = await collection.update_one(
                query,
                {
                    "$set": {
                        "metadata.topics": topics,
                        "updated_at": asyncio.get_event_loop().time()
                    }
                },
                upsert=False  # Don't upsert, only update existing chunks
            )
            
            success = (result.modified_count > 0 or result.upserted_id is not None)
            if success:
                if chunk_id:
                    logger.info(f"Saved {len(topics)} topics in metadata for document {document_id}, chunk {chunk_id}")
                else:
                    logger.info(f"Saved {len(topics)} topics in metadata for document {document_id}")
            
            return success
                
        except Exception as e:
            logger.error(f"Error saving topics for document {document_id}: {e}")
            return False

    async def close(self) -> None:
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")
