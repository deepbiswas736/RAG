import logging
import asyncio

from opentelemetry import trace
from opentelemetry.trace.status import Status, StatusCode

# Absolute imports from the 'app' package root
from app.domain.entities.document import Document
from app.domain.entities.document_chunk import DocumentChunk
from app.domain.repositories.document_repository import DocumentRepository
try:
    from app.domain.services.document_processing_service import DocumentProcessingService
except ImportError:
    from app.application.services.document_processing_service import DocumentProcessingService
try:
    from app.domain.services.chunking_service import ChunkingService
except ImportError:
    from app.application.services.chunking_service import ChunkingService
from app.infrastructure.blob.blob_store import BlobStore
from app.infrastructure.messaging.kafka_client import KafkaClient

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

class BackgroundDocumentProcessor:
    def __init__(
        self,
        document_repository: DocumentRepository, 
        document_processor: DocumentProcessingService,
        blob_store: BlobStore,
        chunking_service: ChunkingService,
        kafka_client: KafkaClient
    ):
        self.document_repository = document_repository
        self.document_processor = document_processor
        self.blob_store = blob_store
        self.chunking_service = chunking_service
        self.kafka_client = kafka_client
        logger.info("BackgroundDocumentProcessor initialized")

    async def process_document_background(self, document_id: str):
        """
        Process document asynchronously: extract text, chunk, request metadata.
        (Formerly _process_document in DocumentService)
        """
        with tracer.start_as_current_span("process_document_background") as span:
            span.set_attribute("document.id", document_id)
            
            try:
                document: Document = await self.document_repository.get_document_by_id(document_id)
                if not document:
                    logger.error(f"Document not found for background processing - document_id: {document_id}")
                    span.set_status(Status(StatusCode.ERROR), "Document not found")
                    return
                
                document.update_processing_status("processing") 
                await self.document_repository.update_document(document)
                
                with tracer.start_as_current_span("extract_text_background") as extract_span:
                    file_content, _ = await self.blob_store.get_file(document.blob_path)
                    structured_content, error = await self.document_processor.extract_text(
                        file_content=file_content.getvalue(),
                        file_extension=f".{document.file_type}"
                    )
                    
                    if error:
                        logger.error(f"Error extracting text from document in background - document_id: {document_id}, error: {error}")
                        extract_span.set_status(Status(StatusCode.ERROR), error)
                        document.update_processing_status("failed", error)
                        await self.document_repository.update_document(document)
                        await self.kafka_client.send_document_processed_event(
                            document_id=document_id, status="failed", metadata={"error": error}
                        )
                        return
                
                document.text_content = structured_content.get('document_text', '')
                if hasattr(document, 'page_contents'): 
                    document.page_contents = structured_content.get('pages', {})
                document = await self.document_repository.update_document(document)
                logger.info(f"Document text content updated for {document_id} in background")

                logger.info(f"Starting chunking for document {document_id} in background")
                await self._chunk_document_internal(document_id, document.text_content)

                document: Document = await self.document_repository.get_document_by_id(document_id) # Re-fetch
                if not document:
                    logger.error(f"Document not found after chunking attempt in background - document_id: {document_id}")
                    span.set_status(Status(StatusCode.ERROR), "Document not found post-chunking")
                    await self.kafka_client.send_document_processed_event(
                        document_id=document_id, status="failed", metadata={"error": "Document not found post-chunking"}
                    )
                    return
                logger.info(f"Chunking completed for document {document_id}. Is chunked: {document.is_chunked}, Chunks: {document.chunk_count}")

                if document.is_chunked and document.chunk_count > 0:
                    with tracer.start_as_current_span("request_metadata_extraction_background") as metadata_span:
                        try:
                            logger.info(f"Requesting metadata extraction for document {document_id} in background")
                            await self.kafka_client.send_metadata_extraction_request(
                                document_id=document.id, document_path=document.blob_path, file_type=document.file_type
                            )
                            metadata_span.set_attribute("document.id", document.id)
                            logger.info(f"Metadata extraction requested successfully after chunking in background - document_id: {document.id}")
                        except Exception as e:
                            logger.error(f"Failed to request metadata extraction after chunking in background - document_id: {document.id}, error: {str(e)}")
                            metadata_span.set_status(Status(StatusCode.ERROR), str(e))
                elif document.is_chunked and document.chunk_count == 0:
                    logger.warning(f"Chunking resulted in 0 chunks for document {document.id}. Skipping metadata extraction.")
                else:                    logger.warning(f"Skipping metadata extraction for document {document.id} as chunking was not successful or produced no chunks. "
                                   f"Chunking error: {document.processing_error}")
                
                final_doc_status = "completed"
                event_status_for_kafka = "completed"
                event_metadata_for_kafka = {}

                if not document.is_chunked:
                    logger.error(f"Document processing completed for {document.id}, but chunking failed. Error: {document.processing_error}")
                    event_status_for_kafka = "failed" 
                    event_metadata_for_kafka["error"] = document.processing_error or "Chunking failed."
                    event_metadata_for_kafka["details"] = "Text extraction succeeded, but chunking failed."
                elif document.chunk_count == 0:
                    logger.warning(f"Document processing completed for {document.id}, text extracted, but 0 chunks created.")
                    event_status_for_kafka = "completed_with_no_chunks"
                    event_metadata_for_kafka["info"] = "Text extraction succeeded, but 0 chunks were created."
                else:
                    logger.info(f"Document processing and chunking completed successfully for {document_id} in background.")

                document.update_processing_status(final_doc_status, document.processing_error)
                await self.document_repository.update_document(document)
                
                await self.kafka_client.send_document_processed_event(
                    document_id=document.id, status=event_status_for_kafka, metadata=event_metadata_for_kafka
                )                
                span.set_status(Status(StatusCode.OK))
                
            except Exception as e:
                logger.error(f"Error processing document in background - document_id: {document_id}, error: {str(e)}")
                span.set_status(Status(StatusCode.ERROR), str(e))
                
                try:
                    doc_to_update: Document = await self.document_repository.get_document_by_id(document_id)
                    if doc_to_update:
                        doc_to_update.update_processing_status("failed", str(e))
                        await self.document_repository.update_document(doc_to_update)
                except Exception as update_error:
                    logger.error(f"Error updating document with error status in background - document_id: {document_id}, error: {str(update_error)}")
                
                await self.kafka_client.send_document_processed_event(
                    document_id=document_id, status="failed", metadata={"error": str(e)}
                )

    async def _chunk_document_internal(self, document_id: str, text: str):
        """
        Chunk document text and save chunks.
        (Formerly _chunk_document in DocumentService)
        """
        try:
            document: Document = await self.document_repository.get_document_by_id(document_id)
            if not document:
                logger.error(f"Document not found for chunking (internal): {document_id}")
                return
            
            await self.document_repository.delete_chunks_by_document_id(document_id)
            
            chunks_data = [] 
            try:
                chunks_data = self.chunking_service.chunk_with_semantic_boundaries(
                    text=text,
                    metadata={
                        "document_id": document_id,
                        "document_name": document.name,
                        "document_type": document.file_type
                    }
                )
            except Exception as e:
                logger.error(f"Error during document chunking service call: {e}, document_id: {document_id}")
                await self.document_repository.update_document_status(
                    document_id=document_id, is_chunked=False, chunk_count=0,
                    processing_error=f"Chunking service failed: {str(e)}"
                )
                return

            if not chunks_data:
                logger.warning(f"No chunks created by chunking service for document: {document_id}")
                await self.document_repository.update_document_status(
                    document_id=document_id, is_chunked=True, chunk_count=0, processing_error=None
                )
                return

            saved_chunks_count = 0
            for i, chunk_item in enumerate(chunks_data):
                try:
                    document_chunk = DocumentChunk( 
                        document_id=document_id,
                        chunk_index=i,
                        text=chunk_item["text"], 
                        metadata=chunk_item.get("metadata", {})
                    )
                    await self.document_repository.save_chunk(document_chunk)
                    saved_chunks_count += 1
                    logger.debug(f"Saved chunk {i} for document {document_id}")
                except Exception as e:
                    logger.error(f"Failed to save chunk {i} for document {document_id}: {e}")
            
            processing_err_msg = None
            if saved_chunks_count < len(chunks_data):
                logger.warning(f"Failed to save {len(chunks_data) - saved_chunks_count} out of {len(chunks_data)} chunks for document {document_id}")
                processing_err_msg = "Partial chunk saving failure"
            else:
                logger.info(f"Successfully processed and saved {saved_chunks_count} chunks for document {document_id}")
            
            await self.document_repository.update_document_status(
                document_id=document_id, is_chunked=True, chunk_count=saved_chunks_count,
                processing_error=processing_err_msg
            )
            
        except Exception as e:
            logger.error(f"Critical error in _chunk_document_internal for {document_id}: {e}")
            try:
                await self.document_repository.update_document_status(
                    document_id=document_id, is_chunked=False, chunk_count=0,
                    processing_error=f"Chunking failed: {str(e)}"
                )
            except Exception as db_error:
                logger.error(f"Failed to update document status after chunking error for {document_id}: {db_error}")

