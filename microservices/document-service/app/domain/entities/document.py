"""
Document Entity
--------------
Represents a document in the system with its metadata and properties.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
import uuid

@dataclass
class Document:
    """Document entity representing any uploadable document"""
    
    # Core properties
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    file_type: str = ""
    file_size: int = 0
    content_type: str = ""
    blob_path: str = ""  # Path in blob storage
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    created_by: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Processing status
    is_processed: bool = False
    is_chunked: bool = False
    processing_status: str = "pending"  # pending, processing, completed, failed
    processing_error: Optional[str] = None
    
    # Chunk information
    chunk_count: int = 0
    embedding_model: Optional[str] = None
    
    @property
    def is_ready_for_query(self) -> bool:
        """Check if document is ready for querying"""
        return self.is_processed and self.is_chunked
    
    def update_processing_status(self, status: str, error: Optional[str] = None):
        """Update processing status of the document"""
        self.processing_status = status
        
        if status == "completed":
            self.is_processed = True
        
        if error:
            self.processing_error = error
            
        self.updated_at = datetime.now()
    
    def update_chunking_status(self, is_chunked: bool, chunk_count: int = 0):
        """Update chunking status of the document"""
        self.is_chunked = is_chunked
        self.chunk_count = chunk_count
        self.updated_at = datetime.now()
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert document to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "file_type": self.file_type,
            "file_size": self.file_size,
            "content_type": self.content_type,
            "blob_path": self.blob_path,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "created_by": self.created_by,
            "metadata": self.metadata,
            "is_processed": self.is_processed,
            "is_chunked": self.is_chunked,
            "processing_status": self.processing_status,
            "processing_error": self.processing_error,
            "chunk_count": self.chunk_count,
            "embedding_model": self.embedding_model
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Document':
        """Create document from dictionary"""
        # Convert string dates back to datetime objects
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
            
        if isinstance(data.get("updated_at"), str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
            
        return cls(**data)


@dataclass
class DocumentChunk:
    """Document chunk entity representing a portion of a document"""
    
    # Core properties
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str = ""
    chunk_index: int = 0
    text: str = ""
    
    # Embedding
    embedding: Optional[List[float]] = None
    embedding_model: Optional[str] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert chunk to dictionary"""
        return {
            "id": self.id,
            "document_id": self.document_id,
            "chunk_index": self.chunk_index,
            "text": self.text,
            "embedding": self.embedding,
            "embedding_model": self.embedding_model,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DocumentChunk':
        """Create chunk from dictionary"""
        return cls(**data)
