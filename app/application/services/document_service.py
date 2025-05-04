from typing import List, Dict
from ...domain.entities.document import Document
from ...domain.services.document_processing_service import DocumentProcessingService
from ...domain.repositories.document_repository import DocumentRepository
from ...domain.value_objects.embedding import Embedding
from dataclasses import dataclass
from datetime import datetime
import logging

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class DocumentDTO:
    title: str
    content: str
    metadata: Dict

@dataclass
class ChunkDTO:
    content: str
    source: str
    metadata: Dict

class DocumentService:
    def __init__(
        self,
        document_repository: DocumentRepository,
        document_processor: DocumentProcessingService
    ):
        self.repository = document_repository
        self.processor = document_processor

    async def process_and_store_document(self, doc_dto: DocumentDTO) -> str:
        # Create domain entity
        document = Document.create(
            title=doc_dto.title,
            content=doc_dto.content,
            metadata=doc_dto.metadata
        )

        # Process document (create chunks and embeddings)
        processed_document = await self.processor.process_document(document)
        
        # Store document first to get its ID
        document_id = await self.repository.save(processed_document)
        
        # Add document_id to each chunk's metadata
        if processed_document.chunks:
            for chunk in processed_document.chunks:
                # Add document_id to chunk metadata to establish relationship
                chunk.metadata.__dict__['document_id'] = document_id
            
            # Now store the chunks with proper document_id
            chunk_ids = await self.repository.save_chunks(processed_document.chunks)
            logger.info(f"Stored {len(chunk_ids)} chunks for document {document_id}")
            
        return document_id

    async def search_similar_chunks(self, query: str, limit: int = 5) -> List[ChunkDTO]:
        # Generate query embedding
        query_embedding = self.processor.encoder.encode(query)
        embedding = Embedding.create(query_embedding.tolist())
        
        # Search for similar chunks
        similar_chunks = await self.repository.search_similar(embedding, limit)
        
        # Convert to DTOs
        return [
            ChunkDTO(
                content=chunk.content,
                source=chunk.source,
                metadata=chunk.metadata.__dict__
            )
            for chunk in similar_chunks
        ]