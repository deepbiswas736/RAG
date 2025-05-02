from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional
from ..value_objects.embedding import Embedding
from ..value_objects.metadata import DocumentMetadata

@dataclass
class Chunk:
    id: str
    content: str
    embedding: Embedding
    metadata: DocumentMetadata
    source: str

@dataclass
class Document:
    id: str
    title: str
    content: str
    chunks: List[Chunk]
    metadata: DocumentMetadata
    created_at: datetime
    updated_at: datetime
    
    @classmethod
    def create(cls, title: str, content: str, metadata: Dict) -> 'Document':
        now = datetime.utcnow()
        return cls(
            id="",  # Will be set by repository
            title=title,
            content=content,
            chunks=[],
            metadata=DocumentMetadata.from_dict(metadata),
            created_at=now,
            updated_at=now
        )