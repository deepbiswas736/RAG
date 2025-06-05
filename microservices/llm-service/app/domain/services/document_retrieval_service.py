"""
Document Retrieval Service
--------------------------
Service to retrieve documents and their chunks from Document Service or MongoDB
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class DocumentRetrievalService:
    """Service for retrieving documents and their chunks"""
    
    def __init__(self, document_client, mongo_client):
        """
        Initialize the Document Retrieval Service
        
        Args:
            document_client: Client for interacting with Document Service
            mongo_client: MongoDB client for direct DB access
        """
        self.document_client = document_client
        self.mongo_client = mongo_client
        
    async def get_document_by_id(self, document_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a document by its ID
        
        Args:
            document_id: Document ID
            
        Returns:
            Document data or None if not found
        """
        try:
            document = await self.mongo_client.get_document_by_id(document_id)
            if document:
                logger.info(f"Retrieved document {document_id} from MongoDB")
                return document
            else:
                logger.warning(f"Document {document_id} not found in MongoDB")
                return None
        except Exception as e:
            logger.error(f"Error retrieving document {document_id} from MongoDB: {e}")
            return None
    
    async def get_document_chunks(self, document_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get chunks for a document
        
        Args:
            document_id: Document ID
            limit: Optional maximum number of chunks to retrieve
            
        Returns:
            List of document chunks
        """

        try:
            chunks = await self.mongo_client.get_document_chunks(document_id, limit)
            if chunks:
                logger.info(f"Retrieved {len(chunks)} chunks for document {document_id} from MongoDB")
                return chunks
            else:
                logger.warning(f"No chunks found for document {document_id} in MongoDB")
                return []
        except Exception as e:
            logger.error(f"Error retrieving chunks for document {document_id} from MongoDB: {e}")
            return []
    
    def get_document_content(self, document_data: Dict[str, Any], chunks: List[Dict[str, Any]]) -> str:
        """
        Extract or construct document content from document data and/or chunks
        
        Args:
            document_data: Document data dictionary
            chunks: List of document chunks
            
        Returns:
            Document content string
        """
        # Try to get content directly from document
        content = document_data.get("content", "") or document_data.get("text_content", "")
        
        # If no content in document, try concatenating chunk contents
        if not content and chunks:
            content = " ".join([chunk.get("content", "") for chunk in chunks if chunk.get("content")])
            
        return content
    
    async def update_document_processing_status(self, document_id: str, status: str, error: Optional[str] = None) -> bool:
        """
        Update document processing status
        
        Args:
            document_id: Document ID
            status: Status string (e.g., "processing", "failed", "completed")
            error: Optional error message
            
        Returns:
            True if update was successful, False otherwise
        """
        metadata = {
            "processing_status": status,
            "last_updated": datetime.utcnow().isoformat()
        }
        
        if error:
            metadata["error"] = error
        
        try:
            # Try Document Service first
            success = await self.document_client.send_document_processed_event(
                document_id=document_id,
                status=status,
                metadata=metadata
            )
            
            if success:
                return True
                
            # Fall back to MongoDB
            return await self.mongo_client.update_document_metadata(document_id, metadata)
            
        except Exception as e:
            logger.error(f"Failed to update document {document_id} status: {e}")
            return False
