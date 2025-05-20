from typing import Dict, Any, Optional, List
import uuid

class DocumentChunk:
    """Represents a chunk of a document with associated metadata"""
    
    def __init__(self, document_id: str, chunk_index: int, text: str, metadata: Dict[str, Any], id: Optional[str] = None, embedding: Optional[List[float]] = None, embedding_model: Optional[str] = None):
        self.id = id or str(uuid.uuid4())
        self.document_id = document_id
        self.chunk_index = chunk_index
        self.text = text
        self.metadata = metadata
        self.embedding = embedding
        self.embedding_model = embedding_model
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert chunk to dictionary representation"""
        return {
            "id": self.id,
            "document_id": self.document_id,
            "chunk_index": self.chunk_index,            "text": self.text,
            "metadata": self.metadata,
            "embedding": self.embedding,
            "embedding_model": self.embedding_model
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DocumentChunk':
        """Create chunk from dictionary"""
        return cls(
            id=data.get("id") or data.get("_id", None),
            document_id=data.get("document_id", ""),
            chunk_index=data.get("chunk_index", 0),
            text=data.get("text", ""),
            metadata=data.get("metadata", {}),
            embedding=data.get("embedding"),
            embedding_model=data.get("embedding_model")
        )
