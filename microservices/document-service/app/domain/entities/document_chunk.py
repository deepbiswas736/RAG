from typing import Dict, Any

class DocumentChunk:
    """Represents a chunk of a document with associated metadata"""
    
    def __init__(self, document_id: str, chunk_index: int, text: str, metadata: Dict[str, Any]):
        self.document_id = document_id
        self.chunk_index = chunk_index
        self.text = text
        self.metadata = metadata
