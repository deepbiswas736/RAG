"""
MongoDB Document Repository
-------------------------
Implementation of the document repository using MongoDB for storage.
"""
import logging
import pymongo
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import PyMongoError
from typing import List, Dict, Optional, Any, Tuple
from bson import ObjectId
from bson.errors import InvalidId
from datetime import datetime
import os

from domain.entities.document import Document, DocumentChunk
from domain.repositories.document_repository import DocumentRepository

# Configure logging
logger = logging.getLogger(__name__)

class MongoDBDocumentRepository(DocumentRepository):
    """MongoDB implementation of the document repository"""
    def __init__(
        self,
        connection_string: Optional[str] = None,
        db_name: Optional[str] = None
    ):
        """
        Initialize MongoDB repository
        
        Args:
            connection_string: MongoDB connection string
            db_name: Database name
        """
        # Prioritize MONGO_URI, then MONGODB_URL, then the default
        self.connection_string = os.getenv("MONGO_URI") or \
                                 os.getenv("MONGODB_URL") or \
                                 connection_string or \
                                 "mongodb://user:password@mongodb:27017/document_service?authSource=admin&replicaSet=rs0&retryWrites=true"
        
        self.db_name = db_name or os.getenv("MONGODB_DB_NAME", "document_db")
        logger.info(f"Attempting to connect to MongoDB with connection string: {self.connection_string}") # Added log
        
        # Connect to MongoDB with replica set awareness
        connect_kwargs = {
            "serverSelectionTimeoutMS": 5000,  # 5 seconds timeout for server selection
            "connectTimeoutMS": 10000,         # 10 seconds connection timeout
            "socketTimeoutMS": 30000,          # 30 seconds socket timeout
            "retryWrites": True,               # Enable retry for write operations
        }
        
        self._client = MongoClient(self.connection_string, **connect_kwargs)
        self._db = self._client[self.db_name]
        
        # Define collections
        self.documents_collection = self._db["documents"]
        self.chunks_collection = self._db["document_chunks"]
        
        # Create indices
        self._create_indices()
        
        logger.info(f"MongoDB repository initialized with database: {self.db_name}")

    def _create_indices(self):
        """Create necessary indices for performance"""
        try:
            # First verify we can connect to MongoDB
            # Use the existing client to ping the server
            self._client.admin.command('ping')
            
            # Document collection indices
            self.documents_collection.create_index([("name", ASCENDING)])
            self.documents_collection.create_index([("processing_status", ASCENDING)])
            self.documents_collection.create_index([("is_chunked", ASCENDING)])
            
            # Chunks collection indices
            self.chunks_collection.create_index([("document_id", ASCENDING)])
            self.chunks_collection.create_index([("chunk_index", ASCENDING)])
            
            logger.info("MongoDB indices created successfully")
        except PyMongoError as e:
            logger.error(f"Error creating MongoDB indices: {e}")
        
    async def save_document(self, document: Document) -> Document:
        """
        Save a document to the repository
        
        Args:
            document: Document to save
            
        Returns:
            Saved document with assigned ID
        """
        try:
            # Convert document to dictionary
            document_dict = document.to_dict()
            
            # MongoDB expects datetime objects, not strings
            if isinstance(document_dict["created_at"], str):
                document_dict["created_at"] = datetime.fromisoformat(document_dict["created_at"])
            if isinstance(document_dict["updated_at"], str):
                document_dict["updated_at"] = datetime.fromisoformat(document_dict["updated_at"])
                
            # Insert the document
            result = self.documents_collection.insert_one(document_dict)
            
            # Update the ID if necessary
            if str(result.inserted_id) != document.id:
                document.id = str(result.inserted_id)
                
            logger.info(f"Document saved with ID: {document.id}")
            return document
            
        except PyMongoError as e:
            logger.error(f"Error saving document: {e}")
            raise
            
    async def get_document_by_id(self, document_id: str) -> Optional[Document]:
        """
        Retrieve a document by its ID
        
        Args:
            document_id: ID of the document
            
        Returns:
            Document object if found, None otherwise
        """
        try:
            # Try to convert string ID to ObjectId
            doc_id = document_id
            if ObjectId.is_valid(document_id):
                doc_id = ObjectId(document_id)
                
            # Query using both forms of ID for compatibility
            query = {"$or": [{"id": document_id}, {"_id": doc_id}]}
            
            # Find the document
            result = self.documents_collection.find_one(query)
            
            if result:
                # If _id is ObjectId, convert to string for our domain model
                if "_id" in result and isinstance(result["_id"], ObjectId):
                    result["id"] = str(result["_id"])
                    
                # Create document object from dictionary
                return Document.from_dict(result)
                
            return None
            
        except (PyMongoError, InvalidId) as e:
            logger.error(f"Error retrieving document {document_id}: {e}")
            raise
            
    async def delete_document(self, document_id: str) -> bool:
        """
        Delete a document from the repository
        
        Args:
            document_id: ID of the document to delete
            
        Returns:
            True if deleted, False otherwise
        """
        try:
            # Try to convert string ID to ObjectId
            doc_id = document_id
            if ObjectId.is_valid(document_id):
                doc_id = ObjectId(document_id)
                
            # Query using both forms of ID for compatibility
            query = {"$or": [{"id": document_id}, {"_id": doc_id}]}
            
            # Delete the document
            result = self.documents_collection.delete_one(query)
            
            # Also delete associated chunks
            self.chunks_collection.delete_many({"document_id": document_id})
            
            return result.deleted_count > 0
            
        except (PyMongoError, InvalidId) as e:
            logger.error(f"Error deleting document {document_id}: {e}")
            raise
            
    async def update_document(self, document: Document) -> Document:
        """
        Update an existing document
        
        Args:
            document: Document to update
            
        Returns:
            Updated document
        """
        try:
            # Convert document to dictionary
            document_dict = document.to_dict()
            
            # MongoDB expects datetime objects, not strings
            if isinstance(document_dict["created_at"], str):
                document_dict["created_at"] = datetime.fromisoformat(document_dict["created_at"])
            if isinstance(document_dict["updated_at"], str):
                document_dict["updated_at"] = datetime.fromisoformat(document_dict["updated_at"])
                
            # Ensure updated_at is fresh
            document_dict["updated_at"] = datetime.now()
                
            # Try to convert string ID to ObjectId
            doc_id = document.id
            if ObjectId.is_valid(document.id):
                doc_id = ObjectId(document.id)
                
            # Query using both forms of ID for compatibility
            query = {"$or": [{"id": document.id}, {"_id": doc_id}]}
                
            # Update the document
            result = self.documents_collection.replace_one(
                query,
                document_dict,
                upsert=True
            )
            
            logger.info(f"Document updated: {document.id}, matched: {result.matched_count}")
            return document
            
        except (PyMongoError, InvalidId) as e:
            logger.error(f"Error updating document {document.id}: {e}")
            raise
            
    async def list_documents(
        self,
        skip: int = 0,
        limit: int = 100,
        query_filter: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[Document], int]:
        """
        List documents with pagination and filtering
        
        Args:
            skip: Number of documents to skip
            limit: Maximum number of documents to return
            query_filter: Filter criteria
            
        Returns:
            Tuple of (list of documents, total count)
        """
        try:
            # Default filter (show all)
            filter_query = query_filter or {}
            
            # Count total documents matching filter
            total_count = self.documents_collection.count_documents(filter_query)
            
            # Get documents with pagination
            cursor = self.documents_collection.find(filter_query) \
                .sort("created_at", DESCENDING) \
                .skip(skip) \
                .limit(limit)
                
            # Convert to Document objects
            documents = []
            for doc in cursor:
                # If _id is ObjectId, convert to string for our domain model
                if "_id" in doc and isinstance(doc["_id"], ObjectId):
                    doc["id"] = str(doc["_id"])
                    
                documents.append(Document.from_dict(doc))
                
            return documents, total_count
            
        except PyMongoError as e:
            logger.error(f"Error listing documents: {e}")
            raise
            
    async def save_chunk(self, chunk: DocumentChunk) -> DocumentChunk:
        """
        Save a document chunk
        
        Args:
            chunk: Chunk to save
            
        Returns:
            Saved chunk with assigned ID
        """
        try:
            # Convert chunk to dictionary
            chunk_dict = chunk.to_dict()
                
            # Insert the chunk
            result = self.chunks_collection.insert_one(chunk_dict)
            
            # Update the ID if necessary
            if str(result.inserted_id) != chunk.id:
                chunk.id = str(result.inserted_id)
                
            logger.info(f"Chunk saved with ID: {chunk.id} for document: {chunk.document_id}")
            return chunk
            
        except PyMongoError as e:
            logger.error(f"Error saving chunk: {e}")
            raise
            
    async def get_chunks_by_document_id(self, document_id: str) -> List[DocumentChunk]:
        """
        Get all chunks for a document
        
        Args:
            document_id: ID of the document
            
        Returns:
            List of document chunks
        """
        try:
            # Find all chunks for the document
            cursor = self.chunks_collection.find(
                {"document_id": document_id}
            ).sort("chunk_index", ASCENDING)
            
            # Convert to DocumentChunk objects
            chunks = []
            for doc in cursor:
                # If _id is ObjectId, convert to string for our domain model
                if "_id" in doc and isinstance(doc["_id"], ObjectId):
                    doc["id"] = str(doc["_id"])
                    
                chunks.append(DocumentChunk.from_dict(doc))
                
            return chunks
            
        except PyMongoError as e:
            logger.error(f"Error retrieving chunks for document {document_id}: {e}")
            raise

    async def delete_chunks_by_document_id(self, document_id: str) -> bool:
        """
        Delete all chunks for a document

        Args:
            document_id: ID of the document
            
        Returns:
            True if any chunks were deleted, False otherwise
        """
        try:
            # Delete all chunks for the document
            result = self.chunks_collection.delete_many({"document_id": document_id})
            
            logger.info(f"Deleted {result.deleted_count} chunks for document {document_id}")
            return result.deleted_count > 0
            
        except PyMongoError as e:
            logger.error(f"Error deleting chunks for document {document_id}: {e}")
            raise
            
    async def search_chunks_by_embedding(
        self,
        embedding: List[float],
        limit: int = 5
    ) -> List[DocumentChunk]:
        """
        Search for chunks by embedding similarity
        
        Args:
            embedding: Query embedding
            limit: Maximum number of results
            
        Returns:
            List of document chunks sorted by similarity
        """
        # This method requires vector search capabilities
        # For this implementation, we would need a MongoDB Atlas cluster with vector search
        # or we could use a different vector database like Milvus or FAISS
        # For now, we'll leave this as a placeholder
        logger.warning("Vector search not implemented in this repository")
        return []
        
    async def update_document_status(
        self, 
        document_id: str, 
        is_chunked: bool, 
        chunk_count: int,
        processing_error: Optional[str] = None
    ) -> bool:
        """
        Update document status fields related to chunking
        
        Args:
            document_id: ID of the document
            is_chunked: Whether the document has been chunked
            chunk_count: Number of chunks created
            processing_error: Optional error message
            
        Returns:
            True if update was successful, False otherwise
        """
        try:
            # Try to convert string ID to ObjectId
            doc_id = document_id
            if ObjectId.is_valid(document_id):
                doc_id = ObjectId(document_id)
                
            # Query using both forms of ID for compatibility
            query = {"$or": [{"id": document_id}, {"_id": doc_id}]}
            
            # Update only the specified fields
            update = {
                "$set": {
                    "is_chunked": is_chunked,
                    "chunk_count": chunk_count,
                    "updated_at": datetime.now()
                }
            }
            
            if processing_error is not None:
                update["$set"]["processing_error"] = processing_error
                
            result = self.documents_collection.update_one(query, update)
            
            logger.info(f"Document status updated: {document_id}, matched: {result.matched_count}")
            return result.matched_count > 0
            
        except (PyMongoError, InvalidId) as e:
            logger.error(f"Error updating document status for {document_id}: {e}")
            raise
