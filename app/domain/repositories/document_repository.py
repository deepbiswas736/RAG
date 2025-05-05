from abc import ABC, abstractmethod
from typing import List, Optional
from ..entities.document import Document, Chunk
from ..value_objects.embedding import Embedding

class DocumentRepository(ABC):
    @abstractmethod
    async def save(self, document: Document) -> str:
        """Save a document and return its ID"""
        pass

    @abstractmethod
    async def find_by_id(self, document_id: str) -> Optional[Document]:
        """Find a document by its ID"""
        pass
        
    @abstractmethod
    async def find_by_checksum(self, checksum: str) -> Optional[Document]:
        """Find a document by its content checksum"""
        pass

    @abstractmethod
    async def save_chunks(self, chunks: List[Chunk]) -> List[str]:
        """Save document chunks and return their IDs"""
        pass

    @abstractmethod
    async def search_similar(self, embedding: Embedding, limit: int = 5) -> List[Chunk]:
        """Find chunks similar to the given embedding"""
        pass

    @abstractmethod
    async def find_chunks_by_document_id(self, document_id: str) -> List[Chunk]:
        """Find all chunks belonging to a document"""
        pass