"""
Metadata Updater
--------------
Service for updating document and chunk metadata
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class MetadataUpdater:
    """Service for updating document and chunk metadata"""
    
    def __init__(self, document_client, mongo_client):
        """
        Initialize the Metadata Updater
        
        Args:
            document_client: Client for interacting with Document Service
            mongo_client: MongoDB client for direct DB access
        """
        self.document_client = document_client
        self.mongo_client = mongo_client
        
    async def update_document_metadata(self, document_id: str, metadata: Dict[str, Any]) -> bool:
        """
        Update document metadata
        
        Args:
            document_id: Document ID
            metadata: Metadata to update
            
        Returns:
            True if update was successful, False otherwise
        """
        try:
            # Try Document Service first
            success = await self.document_client.send_document_processed_event(
                document_id=document_id,
                status="metadata_updated",
                metadata=metadata
            )
            
            if success:
                logger.info(f"Updated metadata for document {document_id} via Document Service")
                return True
                
            # Fall back to MongoDB
            success = await self.mongo_client.update_document_metadata(document_id, metadata)
            if success:
                logger.info(f"Updated metadata for document {document_id} via MongoDB")
                return True
                
            logger.warning(f"Failed to update metadata for document {document_id}")
            return False
            
        except Exception as e:
            logger.error(f"Error updating metadata for document {document_id}: {e}")
            return False
    
    async def update_chunk_metadata(self, chunk_id: str, metadata: Dict[str, Any]) -> bool:
        """
        Update chunk metadata
        
        Args:
            chunk_id: Chunk ID
            metadata: Metadata to update
            
        Returns:
            True if update was successful, False otherwise
        """
        try:
            # Try MongoDB since chunks are often managed at the DB level
            success = await self.mongo_client.update_chunk_metadata(chunk_id, metadata)
            if success:
                logger.info(f"Updated metadata for chunk {chunk_id}")
                return True
                
            logger.warning(f"Failed to update metadata for chunk {chunk_id}")
            return False
            
        except Exception as e:
            logger.error(f"Error updating metadata for chunk {chunk_id}: {e}")
            return False
    
    async def update_document_and_chunks(self, document_id: str, 
                                       document_metadata: Dict[str, Any],
                                       chunks_metadata: List[Dict[str, Any]]) -> bool:
        """
        Update document and chunk metadata in a single operation
        
        Args:
            document_id: Document ID
            document_metadata: Document metadata to update
            chunks_metadata: List of chunk metadata updates (dicts with chunk_id and metadata)
            
        Returns:
            True if any updates were successful, False otherwise
        """
        doc_updated = False
        chunks_updated = 0
        
        # First try the Document Service's batch update method if available
        try:
            success = await self.document_client.send_document_update_event(
                document_id=document_id,
                updated_document_metadata=document_metadata,
                updated_chunks_metadata=chunks_metadata
            )
            
            if success:
                logger.info(f"Updated document {document_id} and chunks via Document Service")
                return True
                
        except AttributeError:
            # Method likely doesn't exist, continue with individual updates
            logger.info("Document Service doesn't support batch updates, falling back to individual updates")
        except Exception as e:
            logger.warning(f"Error using batch update via Document Service: {e}")
        
        # Fall back to MongoDB batch update
        try:
            success = await self.mongo_client.update_document_and_chunks(
                document_id=document_id,
                document_metadata=document_metadata,
                chunks_metadata=chunks_metadata
            )
            
            if success:
                logger.info(f"Updated document {document_id} and chunks via MongoDB")
                return True
                
        except Exception as e:
            logger.warning(f"Error using MongoDB batch update: {e}")
        
        # If both batch methods failed, try individual updates
        try:
            # Update document metadata
            doc_updated = await self.update_document_metadata(document_id, document_metadata)
            
            # Update each chunk's metadata
            for chunk_data in chunks_metadata:
                chunk_id = chunk_data.get("chunk_id")
                metadata = chunk_data.get("metadata")
                
                if not chunk_id or not metadata:
                    continue
                    
                if await self.update_chunk_metadata(chunk_id, metadata):
                    chunks_updated += 1
            
            success = doc_updated or chunks_updated > 0
            if success:
                logger.info(f"Updated document {document_id} and {chunks_updated}/{len(chunks_metadata)} chunks via individual updates")
            
            return success
            
        except Exception as e:
            logger.error(f"Error updating document {document_id} and chunks: {e}")
            return False
    
    async def save_document_topics(self, document_id: str, topics: List[str], 
                                 chunk_id: Optional[str] = None) -> bool:
        """
        Save topics for a document or chunk
        
        Args:
            document_id: Document ID
            topics: List of topics
            chunk_id: Optional chunk ID if topics are for a specific chunk
            
        Returns:
            True if save was successful, False otherwise
        """
        try:
            success = await self.mongo_client.save_document_topics(
                document_id=document_id,
                topics=topics,
                chunk_id=chunk_id
            )
            
            if success:
                if chunk_id:
                    logger.info(f"Saved {len(topics)} topics for document {document_id}, chunk {chunk_id}")
                else:
                    logger.info(f"Saved {len(topics)} document-level topics for document {document_id}")
                return True
                
            logger.warning(f"Failed to save topics for document {document_id}")
            return False
            
        except Exception as e:
            logger.error(f"Error saving topics for document {document_id}: {e}")
            return False
