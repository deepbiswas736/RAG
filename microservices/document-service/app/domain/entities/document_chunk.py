from typing import Dict, Any

class DocumentChunk:
    """Represents a chunk of a document with associated metadata"""
    
    def __init__(self, document_id: str, chunk_index: int, text: str, metadata: Dict[str, Any]):
        self.document_id = document_id
        self.chunk_index = chunk_index
        self.text = text
        self.metadata = metadata
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert chunk to dictionary representation"""
        return {
            "document_id": self.document_id,
            "chunk_index": self.chunk_index,
            "text": self.text,
            "metadata": self.metadata
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DocumentChunk':
        """Create chunk from dictionary"""
        return cls(
            document_id=data.get("document_id", ""),
            chunk_index=data.get("chunk_index", 0),
            text=data.get("text", ""),
            metadata=data.get("metadata", {})
        )
