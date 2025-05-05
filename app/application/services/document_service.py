from typing import List, Dict, Optional, Tuple
from ...domain.entities.document import Document, Chunk
from ...domain.services.document_processing_service import DocumentProcessingService
from ...domain.services.query_preprocessor import QueryPreprocessor
from ...domain.services.query_enhancer import QueryEnhancer
from ...domain.services.reranking.reranker import ReRanker
from ...domain.repositories.document_repository import DocumentRepository
from ...domain.value_objects.embedding import Embedding
from ...domain.utils.checksum_util import ChecksumUtil
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
        document_processor: DocumentProcessingService,
        query_preprocessor: Optional[QueryPreprocessor] = None,
        reranker: Optional[ReRanker] = None,
        query_enhancer: Optional[QueryEnhancer] = None
    ):
        self.repository = document_repository
        self.processor = document_processor
        self.query_preprocessor = query_preprocessor
        self.reranker = reranker
        self.query_enhancer = query_enhancer
        
        # Create preprocessor if not provided
        if self.query_preprocessor is None:
            self.query_preprocessor = QueryPreprocessor()
            logger.info("Created default QueryPreprocessor")

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

    async def process_and_store_document_with_checksum(self, doc_dto: DocumentDTO) -> Dict:
        """
        Process and store a document with checksum verification to prevent duplicates.
        
        Args:
            doc_dto: Document data transfer object
            
        Returns:
            Dictionary with document_id and is_duplicate flag
        """
        # Generate checksum for the document content
        checksum = ChecksumUtil.generate_checksum(doc_dto.content)
        
        # Add checksum to metadata
        if not doc_dto.metadata:
            doc_dto.metadata = {}
        doc_dto.metadata['checksum'] = checksum
        
        # Check if document with this checksum already exists
        existing_document = await self.find_document_by_checksum(checksum)
        
        if existing_document:
            logger.info(f"Document with checksum {checksum} already exists (ID: {existing_document.id})")
            return {
                "document_id": existing_document.id,
                "is_duplicate": True,
                "checksum": checksum
            }
        
        # If no duplicate found, proceed with document processing and storage
        logger.info(f"No duplicate found for checksum {checksum}, processing new document")
        document_id = await self.process_and_store_document(doc_dto)
        
        return {
            "document_id": document_id,
            "is_duplicate": False,
            "checksum": checksum
        }
    
    async def find_document_by_checksum(self, checksum: str) -> Optional[Document]:
        """
        Find a document by its content checksum.
        
        Args:
            checksum: Document content checksum
            
        Returns:
            Document if found, None otherwise
        """
        if not checksum:
            return None
            
        try:
            # Query repository for document with matching checksum
            return await self.repository.find_by_checksum(checksum)
        except Exception as e:
            logger.error(f"Error finding document by checksum: {e}")
            return None

    async def search_similar_chunks(
        self, 
        query: str, 
        limit: int = 5,
        rerank: bool = True,
        use_query_enhancement: bool = True
    ) -> List[ChunkDTO]:
        """
        Search for chunks similar to the query with improved precision.
        
        Args:
            query: User query
            limit: Number of results to return
            rerank: Whether to apply reranking for better precision
            use_query_enhancement: Whether to apply query enhancement
            
        Returns:
            List of relevant chunks as DTOs
        """
        working_query = query
        enhancement_info = None
        
        # Step 1: Apply query enhancement if enabled
        if use_query_enhancement and self.query_enhancer:
            try:
                enhancement_result = await self.query_enhancer.enhance(query)
                if enhancement_result and "enhanced_query" in enhancement_result:
                    working_query = enhancement_result["enhanced_query"]
                    enhancement_info = enhancement_result
                    logger.info(f"Query enhanced: '{query}' -> '{working_query}'")
            except Exception as e:
                logger.error(f"Error during query enhancement: {e}")
                # Continue with original query if enhancement fails
        
        # Step 2: Preprocess the enhanced query
        processed_query_data = await self.query_preprocessor.preprocess(working_query)
        processed_query = processed_query_data["processed_query"]
        
        # Step 3: Generate query embedding
        query_embedding = self.processor.encoder.encode(processed_query)
        embedding = Embedding.create(query_embedding.tolist())
        
        # Step 4: Retrieve more chunks if reranking is enabled
        initial_limit = limit * 3 if rerank and self.reranker else limit
        
        # Step 5: Search for similar chunks
        similar_chunks = await self.repository.search_similar(embedding, initial_limit)
        
        # Step 6: Apply reranking if enabled and reranker is available
        if rerank and self.reranker and similar_chunks:
            try:
                logger.info(f"Reranking {len(similar_chunks)} chunks")
                reranked_results = await self.reranker.rerank(
                    query=processed_query, 
                    chunks=similar_chunks,
                    top_k=limit
                )
                
                # Extract chunks from reranked results
                similar_chunks = [chunk for chunk, score in reranked_results]
                logger.info(f"Returning {len(similar_chunks)} reranked chunks")
            except Exception as e:
                logger.error(f"Error during reranking: {e}")
                # Fall back to vector search results if reranking fails
                if len(similar_chunks) > limit:
                    similar_chunks = similar_chunks[:limit]
        
        # Add enhancement info to chunk metadata if available
        if enhancement_info and similar_chunks:
            for chunk in similar_chunks:
                if not hasattr(chunk.metadata, "__dict__"):
                    continue
                    
                # Add only key enhancement details to avoid metadata bloat
                chunk.metadata.__dict__["query_enhancement"] = {
                    "technique": enhancement_info.get("technique", "unknown"),
                    "original_query": enhancement_info.get("original_query", query)
                }
                
                # Add expansion terms if available
                if "expansion_terms" in enhancement_info:
                    chunk.metadata.__dict__["query_enhancement"]["expansion_terms"] = enhancement_info["expansion_terms"]
        
        # Convert to DTOs
        return [
            ChunkDTO(
                content=chunk.content,
                source=chunk.source,
                metadata=chunk.metadata.__dict__
            )
            for chunk in similar_chunks
        ]