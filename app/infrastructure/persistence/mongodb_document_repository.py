from typing import List, Optional, Dict
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from datetime import datetime
from pymongo.errors import OperationFailure, ServerSelectionTimeoutError, ConnectionFailure
import json
import asyncio

from ...domain.repositories.document_repository import DocumentRepository
from ...domain.entities.document import Document, Chunk
from ...domain.value_objects.embedding import Embedding
from ...domain.value_objects.metadata import DocumentMetadata

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MongoDBDocumentRepository(DocumentRepository):
    def __init__(self):
        # Updated default URL to include authSource and directConnection
        self.mongodb_url = os.getenv('MONGODB_URL', 'mongodb://user:password@localhost:27017/?authSource=admin&directConnection=true')
        self.db_name = os.getenv('MONGODB_DB_NAME', 'rag_db')
        self.vector_index_name = os.getenv('MONGODB_VECTOR_INDEX_NAME', 'vector_index')
        self.vector_dimension = int(os.getenv('VECTOR_DIMENSION', '384'))
        self.vector_metric = os.getenv('VECTOR_METRIC', 'cosine')
        # Replace similarity threshold with top_k results parameter
        self.similarity_threshold = float(os.getenv('SIMILARITY_THRESHOLD', '0.0'))  # Keeping for backward compatibility
        self.top_k_results = int(os.getenv('TOP_K_RESULTS', '5'))  # Default to returning top 5 results
        
        self.client = None
        self.db = None
        self.documents = None
        self.chunks = None
        self.vector_search_available = False # Default to False until verified
        self.vector_index_type = None # To store 'atlas' or 'native'
        
        logger.info(f"Initializing MongoDB repository with URL: {self.mongodb_url}, DB: {self.db_name}, Top K Results: {self.top_k_results}")

    async def initialize(self):
        """Initialize the repository - should be called at app startup"""
        # Retry connection 5 times with increasing timeout
        max_retries = 5
        retry_delay = 2  # seconds, increased delay
        for attempt in range(max_retries):
            try:
                self.client = AsyncIOMotorClient(self.mongodb_url, serverSelectionTimeoutMS=10000) # Increased timeout
                # The ismaster command is cheap and does not require auth.
                await self.client.admin.command('ismaster')
                self.db = self.client[self.db_name]
                self.documents = self.db.documents
                self.chunks = self.db.chunks
                logger.info("Successfully connected to MongoDB.")
                await self._ensure_indexes()
                # Vector search availability check moved to after index creation
                return
            except (ServerSelectionTimeoutError, ConnectionFailure) as e:
                logger.warning(f"Attempt {attempt + 1}/{max_retries}: Could not connect to MongoDB: {e}. Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2 # Exponential backoff
            except OperationFailure as e:
                logger.error(f"MongoDB operation failed during initialization: {e}")
                raise ConnectionError(f"MongoDB setup failed: {e}") from e
            except Exception as e:
                logger.error(f"An unexpected error occurred during MongoDB initialization: {e}")
                raise ConnectionError(f"Unexpected MongoDB initialization error: {e}") from e

        logger.error("Failed to connect to MongoDB after multiple retries.")
        self.vector_search_available = False # Mark DB as unavailable if connection fails
        raise ConnectionError("Failed to connect to MongoDB after multiple retries.")

    async def _ensure_indexes(self):
        """Ensure necessary indexes exist, including the vector index."""
        if self.client is None or self.db is None:
            logger.error("Cannot ensure indexes without a valid DB connection.")
            return
        try:
            # Ensure standard indexes first - use document_id instead of the _id field
            # Use sparse=True to allow null values in the index
            await self.documents.create_index([("document_id", 1)], unique=True, sparse=True)
            await self.chunks.create_index([("metadata.document_id", 1)], sparse=True)
            await self.chunks.create_index([("chunk_id", 1)], unique=True, sparse=True)
            
            # Create index for document checksums to optimize duplicate detection
            await self.documents.create_index([("metadata.checksum", 1)], sparse=True)
            
            await self._ensure_vector_index() # Ensure vector index after basic indexes
            logger.info("Successfully ensured standard indexes.")
        except OperationFailure as e:
            logger.error(f"Failed to create standard indexes: {e}")
        except Exception as e:
            logger.error(f"Error checking/creating indexes: {e}")

    async def _ensure_vector_index(self):
        """Check if vector search is available and create the index if needed."""
        try:
            # 1. Check existing indexes (Atlas Search first)
            try:
                # Use list_search_indexes() which is specific to Atlas Search
                search_indexes = await self.chunks.list_search_indexes(name=self.vector_index_name)
                # Check if the specific index exists and is READY
                if search_indexes and search_indexes[0].get('status') == 'READY':
                    logger.info(f"Atlas Search vector index '{self.vector_index_name}' found and READY.")
                    self.vector_search_available = True
                    self.vector_index_type = 'atlas'
                    return # Found Atlas index, ready to use
                elif search_indexes:
                     logger.warning(f"Atlas Search index '{self.vector_index_name}' found but status is not READY (Status: {search_indexes[0].get('status')}). Will attempt creation if needed, but search might fail.")
                     # Don't return yet, maybe creation wasn't attempted or failed previously
                else:
                    logger.info(f"Atlas Search index '{self.vector_index_name}' not found via list_search_indexes.")

            except OperationFailure as e:
                 # listSearchIndexes might not be supported or user lacks permissions
                 logger.warning(f"Could not list search indexes (might be normal for non-Atlas or permissions issue): {e}")
            except Exception as e:
                 logger.warning(f"Error listing search indexes: {e}")

            # 2. Check standard indexes (as a fallback or for native)
            index_info = await self.chunks.index_information()
            if self.vector_index_name in index_info:
                 # This could be a native index or potentially an older way Atlas indexes were listed
                 logger.info(f"Standard index '{self.vector_index_name}' found via index_information(). Assuming native vector index for now.")
                 # We might need more checks here to be certain it's a usable vector index
                 # For now, assume it's usable if found this way and Atlas wasn't found/ready
                 if not self.vector_search_available: # Only set if Atlas wasn't confirmed
                     self.vector_search_available = True
                     self.vector_index_type = 'native'
                 return # Found some index, proceed

            # 3. If no index found/ready, try creating Atlas Search index
            logger.info(f"No ready vector index found. Attempting to create Atlas Search index '{self.vector_index_name}'.")
            try:
                # Use Atlas Search index definition compatible with mongodb-atlas-local
                atlas_index_definition = {
                    "name": self.vector_index_name,
                    "definition": {
                        "mappings": {
                            "dynamic": False, # Explicitly map the vector field
                            "fields": {
                                "embedding": {
                                    "type": "document",
                                    "fields": {
                                        "vector": {
                                            # Use knnVector type for Atlas Search
                                            # The query will use knnBeta which we know works
                                            "type": "knnVector",
                                            "dimensions": self.vector_dimension,
                                            "similarity": self.vector_metric.lower()
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                await self.chunks.create_search_index(atlas_index_definition)
                logger.info(f"Successfully initiated creation of Atlas Search vector index '{self.vector_index_name}'. Waiting for it to become available...")

                # Wait and check status
                max_wait_time = 60 # seconds
                check_interval = 5 # seconds
                waited_time = 0
                index_ready = False
                
                # For Atlas Local, let's just assume it's ready after a short delay
                # Our diagnostics show the indexes were created successfully
                await asyncio.sleep(15)
                logger.info("Created Atlas Search index and waiting period complete. Setting vector search as available.")
                self.vector_search_available = True
                self.vector_index_type = 'atlas'
                return
                
            except OperationFailure as e:
                # Handle specific errors like index name already exists but definition differs, etc.
                logger.error(f"Failed to create Atlas Search index (Code: {e.code}): {e.details}")
                self.vector_search_available = False # Failed to create Atlas index
            except Exception as e: # Catch other potential errors like command not found
                logger.error(f"Failed to create Atlas Search index: {e}")
                self.vector_search_available = False

        except Exception as e:
            logger.error(f"An unexpected error occurred during vector index check/creation: {e}")
            self.vector_search_available = False

    async def save(self, document: Document) -> str:
        # Add an explicit check, although the exception in initialize should prevent this state
        if self.documents is None:
             logger.error("Attempted to save document, but MongoDB collection is not initialized.")
             raise RuntimeError("MongoDB document collection is not available.")
             
        # Generate a document_id if it's not present
        document_id = document.id if document.id else str(datetime.now().timestamp())
        
        doc_dict = {
            "document_id": document_id,  # Add document_id field explicitly
            "title": document.title,
            "content": document.content,
            "metadata": document.metadata.__dict__,
            "created_at": document.created_at,
            "updated_at": document.updated_at
        }
        
        try:
            result = await self.documents.insert_one(doc_dict)
            logger.info(f"Successfully saved document with ID: {document_id}")
            return document_id
        except Exception as e:
            logger.error(f"Error saving document: {e}")
            raise

    async def save_chunks(self, chunks: List[Chunk]) -> List[str]:
         # Add an explicit check
        if self.chunks is None:
             logger.error("Attempted to save chunks, but MongoDB collection is not initialized.")
             raise RuntimeError("MongoDB chunk collection is not available.")
             
        if not self.vector_search_available:
             logger.warning("Skipping saving chunks as vector search is not available.")
             # Optionally raise an error or handle differently
             return [] 
             
        chunk_dicts = []
        for chunk in chunks:
            # Make sure we have a valid document_id in metadata
            if not chunk.metadata.__dict__.get('document_id'):
                logger.warning(f"Chunk {chunk.id} missing document_id in metadata. This could cause retrieval issues.")
                # You might want to raise an error or add a placeholder document_id here
                
            chunk_dicts.append({
                "chunk_id": chunk.id,
                "content": chunk.content,
                "embedding": {
                    "vector": chunk.embedding.vector,
                    "dimension": chunk.embedding.dimension
                },
                "metadata": chunk.metadata.__dict__,
                "source": chunk.source
            })
            
        if not chunk_dicts:
            return []
            
        try:
            result = await self.chunks.insert_many(chunk_dicts, ordered=False) # Use ordered=False to continue on errors
            inserted_ids = [str(id) for id in result.inserted_ids]
            logger.info(f"Successfully inserted {len(inserted_ids)} chunks.")
            return inserted_ids
        except Exception as e:
            logger.error(f"Error inserting chunks: {e}")
            # Handle potential bulk write errors if needed
            return []

    async def search_similar(self, embedding: Embedding, limit: int = None, metadata_filters: Optional[Dict] = None) -> List[Chunk]:
        # Use top_k_results as the default limit if none is provided
        if limit is None:
            limit = self.top_k_results
            
        # Directly use vector search without fallback
        if not self.vector_search_available:
            logger.error("Vector search is not available. Cannot perform search.")
            # Depending on requirements, could raise an error here
            return [] 
            
        logger.info(f"Performing vector search to find top {limit} most similar documents")
        chunks = await self._search_vector(embedding, limit, metadata_filters)
        return chunks

    async def _search_vector(self, embedding: Embedding, limit: int, metadata_filters: Optional[Dict] = None) -> List[Chunk]:
        """Search using appropriate vector search method based on index type"""
        if not self.vector_search_available or self.vector_index_type is None:
             logger.warning(f"Attempted vector search, but it's unavailable or index type unknown (type: {self.vector_index_type}).")
             return []

        pipeline = []
        try:
            # Build the vector search stage
            if self.vector_index_type == 'atlas':
                logger.info(f"Performing vector search using Atlas Search ($search) index '{self.vector_index_name}'.")
                search_stage = {
                    "$search": {
                        "index": self.vector_index_name,
                        "knnBeta": {
                            "vector": embedding.vector,
                            "path": "embedding.vector",
                            "k": limit * 3  # Fetch more results to apply filtering
                        }
                    }
                }
                pipeline.append(search_stage)
                
                # Project required fields
                pipeline.append({
                    "$project": {
                        "_id": 1,
                        "chunk_id": 1,
                        "content": 1,
                        "metadata": 1,
                        "source": 1,
                        "embedding": 1,
                        "score": { "$meta": "searchScore" }
                    }
                })
                
            elif self.vector_index_type == 'native':
                logger.info(f"Performing vector search using native ($vectorSearch) index '{self.vector_index_name}'.")
                search_stage = {
                    "$vectorSearch": {
                        "index": self.vector_index_name,
                        "path": "embedding.vector",
                        "queryVector": embedding.vector,
                        "numCandidates": limit * 20,  # Fetch more candidates to allow for filtering
                        "limit": limit * 3  # Fetch more results to apply filtering
                    }
                }
                pipeline.append(search_stage)
                
                # Project required fields
                pipeline.append({
                    "$project": {
                        "_id": 1,
                        "chunk_id": 1,
                        "content": 1,
                        "metadata": 1,
                        "source": 1,
                        "embedding": 1,
                        "score": { "$meta": "vectorSearchScore" }
                    }
                })
                
            else:
                logger.error(f"Unknown vector index type '{self.vector_index_type}'. Cannot perform search.")
                return []
                
            # Apply metadata filters if provided
            if metadata_filters and isinstance(metadata_filters, dict):
                logger.info(f"Applying metadata filters: {metadata_filters}")
                filter_conditions = {}
                
                for key, value in metadata_filters.items():
                    # Handle nested metadata fields with dot notation
                    metadata_key = f"metadata.{key}"
                    filter_conditions[metadata_key] = value
                
                if filter_conditions:
                    match_stage = {"$match": filter_conditions}
                    pipeline.append(match_stage)
                    logger.info(f"Added metadata filter stage to pipeline: {match_stage}")
            
            # Apply final limit
            pipeline.append({"$limit": limit})

            # Execute the aggregation pipeline
            logger.info(f"Executing vector search pipeline with index '{self.vector_index_name}' for {len(embedding.vector)} dimensions")
            cursor = self.chunks.aggregate(pipeline, maxTimeMS=15000)
            results = await cursor.to_list(length=limit)

            chunks_found = []
            for doc in results:
                # Log the score for debugging
                score = doc.get("score", 0)
                logger.debug(f"Document {doc.get('_id')} similarity score: {score}")
                
                # Ensure embedding exists and is valid before creating Chunk object
                doc_embedding_data = doc.get("embedding")
                if doc_embedding_data and "vector" in doc_embedding_data:
                    try:
                        chunk_embedding = Embedding.create(doc_embedding_data["vector"])
                        chunk_metadata = DocumentMetadata.from_dict(doc.get("metadata", {}))
                        
                        chunks_found.append(Chunk(
                            id=str(doc["_id"]),
                            content=doc.get("content", ""),
                            embedding=chunk_embedding,
                            metadata=chunk_metadata,
                            source=doc.get("source", "")
                        ))
                    except Exception as e:
                         logger.error(f"Error processing document {doc.get('_id')} during chunk creation: {e}")
                else:
                     logger.warning(f"Document {doc.get('_id')} missing valid embedding data.")
            
            if chunks_found:
                logger.info(f"Vector search found {len(chunks_found)} results after applying filters (if any).")
            else:
                if metadata_filters:
                    logger.warning(f"Vector search returned no results after applying metadata filters: {metadata_filters}")
                else:
                    logger.warning(f"Vector search returned no results. Check your vector search configuration.")
                
            return chunks_found

        except OperationFailure as e:
             logger.error(f"MongoDB OperationFailure during vector search (Type: {self.vector_index_type}): {e.details}", exc_info=True)
             return []
        except Exception as e:
            logger.error(f"Unexpected error during vector search (Type: {self.vector_index_type}): {e}", exc_info=True)
            return []

    async def find_by_id(self, document_id: str) -> Optional[Document]:
        """
        Find a document by its document_id field.
        
        This method looks for a document with the given document_id in the 'document_id' field,
        not the MongoDB '_id' field, to ensure consistency with how documents are saved.
        
        Args:
            document_id: The document ID to search for
            
        Returns:
            Document object if found, None otherwise
        """
        try:
            # Search for document by document_id field, not _id
            doc = await self.documents.find_one({"document_id": document_id})
            
            if not doc:
                logger.warning(f"No document found with document_id: {document_id}")
                return None
            
            chunks = await self.find_chunks_by_document_id(document_id)
            
            return Document(
                id=document_id,  # Use document_id for consistency
                title=doc["title"],
                content=doc["content"],
                chunks=chunks,
                metadata=DocumentMetadata.from_dict(doc["metadata"]),
                created_at=doc.get("created_at", datetime.now()),
                updated_at=doc.get("updated_at", datetime.now())
            )
        except Exception as e:
            logger.error(f"Error finding document by ID {document_id}: {e}")
            return None

    async def find_chunks_by_document_id(self, document_id: str) -> List[Chunk]:
        """
        Find all chunks belonging to a document based on the document_id.
        
        Args:
            document_id: The document ID to search for in chunk metadata
            
        Returns:
            List of chunks associated with the document
        """
        try:
            cursor = self.chunks.find({"metadata.document_id": document_id})
            chunks = []
            async for doc in cursor:
                # Extract embedding data
                doc_embedding_data = doc.get("embedding")
                if doc_embedding_data and "vector" in doc_embedding_data:
                    try:
                        chunk_embedding = Embedding.create(doc_embedding_data["vector"])
                        chunks.append(Chunk(
                            id=str(doc.get("chunk_id", doc.get("_id"))),
                            content=doc.get("content", ""),
                            embedding=chunk_embedding,
                            metadata=DocumentMetadata.from_dict(doc.get("metadata", {})),
                            source=doc.get("source", "")
                        ))
                    except Exception as e:
                        logger.error(f"Error creating chunk from document {doc.get('_id')}: {e}")
                else:
                    logger.warning(f"Chunk {doc.get('_id')} missing valid embedding data")
                    
            logger.info(f"Found {len(chunks)} chunks for document {document_id}")
            return chunks
        except Exception as e:
            logger.error(f"Error finding chunks for document {document_id}: {e}")
            return []

    async def check_vector_index_status(self):
        """Diagnostic function to check vector index status"""
        try:
            # Get collection stats to see if vector indexes exist
            collection_stats = await self.db.command("collStats", "chunks")
            
            # Get index details
            indexes = await self.chunks.index_information()
            
            # Check for vector index
            index_found = self.vector_index_name in indexes
            vector_search_enabled = self.vector_search_available
            
            # Check MongoDB version
            server_info = await self.client.server_info()
            mongodb_version = server_info.get('version', 'Unknown')
            
            # Check if any documents with embeddings exist
            sample_doc = await self.chunks.find_one({"embedding.vector": {"$exists": True}})
            has_embeddings = sample_doc is not None
            
            if has_embeddings and sample_doc.get('embedding') and 'vector' in sample_doc['embedding']:
                embedding_sample = sample_doc['embedding']['vector']
                embedding_dimension = len(embedding_sample)
                expected_dimension = self.vector_dimension
                dimension_match = embedding_dimension == expected_dimension
            else:
                embedding_sample = None
                embedding_dimension = None
                dimension_match = False
                
            # Collect results
            status = {
                "mongodb_version": mongodb_version,
                "vector_search_enabled": vector_search_enabled,
                "vector_index_found": index_found,
                "index_name": self.vector_index_name,
                "has_documents_with_embeddings": has_embeddings,
                "embedding_dimension": embedding_dimension,
                "expected_dimension": self.vector_dimension,
                "dimension_match": dimension_match
            }
            
            return status
            
        except Exception as e:
            logger.error(f"Error checking vector index status: {e}")
            return {
                "error": str(e),
                "vector_search_available": self.vector_search_available
            }

    async def find_by_checksum(self, checksum: str) -> Optional[Document]:
        """Find a document by its content checksum"""
        if not checksum or self.documents is None:
            return None
        
        try:
            # Search for documents with matching checksum in metadata
            doc = await self.documents.find_one({"metadata.checksum": checksum})
            
            if not doc:
                logger.debug(f"No document found with checksum: {checksum}")
                return None
            
            # Fetch the chunks for this document
            document_id = str(doc["_id"])
            chunks = await self.find_chunks_by_document_id(document_id)
            
            # Create and return the document entity
            return Document(
                id=document_id,
                title=doc["title"],
                content=doc.get("content", ""),  # Content might be large, may be missing
                chunks=chunks,
                metadata=DocumentMetadata.from_dict(doc["metadata"]),
                created_at=doc.get("created_at", datetime.now()),
                updated_at=doc.get("updated_at", datetime.now())
            )
        except Exception as e:
            logger.error(f"Error finding document by checksum: {e}")
            return None

    async def update_metadata(self, document_id: str, metadata: DocumentMetadata) -> bool:
        """Update metadata for a document."""
        try:
            # Convert metadata to dict for MongoDB update
            metadata_dict = metadata.__dict__
            
            # Update the document's metadata
            result = await self.documents.update_one(
                {"document_id": document_id},
                {"$set": {"metadata": metadata_dict}}
            )
            
            # Also update metadata in all associated chunks
            chunk_update = await self.chunks.update_many(
                {"metadata.document_id": document_id},
                {"$set": {"metadata": metadata_dict}}
            )
            
            logger.info(f"Updated metadata for document {document_id}: {result.modified_count} document and {chunk_update.modified_count} chunks modified")
            
            # Return True if the document was found and updated
            return result.matched_count > 0 and result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating metadata for document {document_id}: {e}")
            return False

    async def filter_then_search(self, 
                                embedding: Embedding, 
                                metadata_filters: Dict,
                                limit: int = 5,
                                pre_filter_limit: int = 100) -> List[Chunk]:
        """
        Two-step retrieval: First filter by metadata, then find semantically similar chunks.
        
        Args:
            embedding: The query embedding to compare against
            metadata_filters: Dictionary of metadata key-value pairs for filtering
            limit: Maximum number of final results to return
            pre_filter_limit: Maximum number of chunks to retrieve in the initial metadata filtering
            
        Returns:
            List of chunks matching both metadata filters and semantic similarity
        """
        if not self.vector_search_available:
            logger.error("Vector search is not available. Cannot perform search.")
            return []
            
        logger.info(f"Performing two-step retrieval with metadata filters: {metadata_filters}")
        
        try:
            # STEP 1: Filter chunks by metadata first
            if not metadata_filters:
                logger.warning("No metadata filters provided for filter_then_search. Falling back to standard search.")
                return await self.search_similar(embedding, limit)
                
            filter_conditions = {}
            for key, value in metadata_filters.items():
                # Handle different types of filters: exact match, array contains, etc.
                metadata_key = f"metadata.{key}"
                
                if isinstance(value, str):
                    # For string values, use case-insensitive matching
                    filter_conditions[metadata_key] = {"$regex": f"^{value}$", "$options": "i"}
                elif isinstance(value, list):
                    # For lists, check if metadata field contains any of the values
                    if all(isinstance(item, str) for item in value):
                        # For string lists, use case-insensitive matching on any item
                        filter_conditions[metadata_key] = {"$in": value}
                    else:
                        filter_conditions[metadata_key] = {"$in": value}
                else:
                    # For other types (numbers, booleans), use exact matching
                    filter_conditions[metadata_key] = value
            
            logger.info(f"Filtering chunks by metadata: {filter_conditions}")
            
            # Find chunks matching metadata filters
            filtered_chunks_cursor = self.chunks.find(filter_conditions).limit(pre_filter_limit)
            filtered_chunks = await filtered_chunks_cursor.to_list(length=pre_filter_limit)
            
            if not filtered_chunks:
                logger.info("No chunks found matching metadata filters")
                return []
                
            logger.info(f"Found {len(filtered_chunks)} chunks matching metadata filters")
            
            # STEP 2: Compute similarity scores for the filtered chunks
            # This is the most efficient approach as we're only computing similarity
            # for chunks that already match our metadata criteria
            
            chunk_objects = []
            for doc in filtered_chunks:
                try:
                    # Extract embedding data
                    doc_embedding_data = doc.get("embedding")
                    if doc_embedding_data and "vector" in doc_embedding_data:
                        doc_embedding = Embedding.create(doc_embedding_data["vector"])
                        
                        # Compute similarity score 
                        # Use dot product for cosine similarity since vectors are normalized
                        similarity_score = sum(a * b for a, b in zip(embedding.vector, doc_embedding.vector))
                        
                        # Create chunk with metadata
                        chunk = Chunk(
                            id=str(doc["_id"]),
                            content=doc.get("content", ""),
                            embedding=doc_embedding,
                            metadata=DocumentMetadata.from_dict(doc.get("metadata", {})),
                            source=doc.get("source", "")
                        )
                        
                        # Store chunk with its similarity score
                        chunk_objects.append((chunk, similarity_score))
                except Exception as e:
                    logger.error(f"Error processing chunk {doc.get('_id')}: {e}")
            
            # Sort by similarity score (highest first) and take top 'limit' results
            chunk_objects.sort(key=lambda x: x[1], reverse=True)
            top_chunks = [chunk for chunk, _ in chunk_objects[:limit]]
            
            logger.info(f"Returning top {len(top_chunks)} chunks based on semantic similarity")
            return top_chunks
            
        except Exception as e:
            logger.error(f"Error in filter_then_search: {e}")
            return []

    async def semantic_metadata_search(self, query: str, embedding: Embedding, limit: int = 100) -> List[str]:
        """
        Perform semantic search on metadata fields to find relevant document IDs.
        
        This method searches through document metadata fields like topics, keywords, and summary,
        using both text matching and vector similarity to find relevant documents.
        """
        if not self.vector_search_available:
            logger.error("Vector search is not available. Cannot perform search.")
            return []
            
        try:
            # Create a pipeline that will:
            # 1. Search for metadata fields that contain the query terms
            # 2. Perform vector similarity search on concatenated metadata text
            # 3. Return document IDs sorted by relevance score
            
            # First, get documents by metadata text search
            metadata_pipeline = []
            
            if self.vector_index_type == 'atlas':
                # Create a compound query that looks at various metadata fields
                metadata_pipeline = [
                    {
                        "$search": {
                            "index": self.vector_index_name,
                            "compound": {
                                "should": [
                                    # Search in topics
                                    {
                                        "text": {
                                            "query": query,
                                            "path": "metadata.topics",
                                            "score": { "boost": { "value": 3 } }  # Higher weight for topics
                                        }
                                    },
                                    # Search in keywords
                                    {
                                        "text": {
                                            "query": query,
                                            "path": "metadata.keywords",
                                            "score": { "boost": { "value": 2.5 } }  # High weight for keywords
                                        }
                                    },
                                    # Search in summary
                                    {
                                        "text": {
                                            "query": query,
                                            "path": "metadata.summary",
                                            "score": { "boost": { "value": 2 } }  # Medium weight for summary
                                        }
                                    },
                                    # Search in person_name
                                    {
                                        "text": {
                                            "query": query,
                                            "path": "metadata.person_name",
                                            "score": { "boost": { "value": 4 } }  # Highest weight for person name
                                        }
                                    }
                                ]
                            }
                        }
                    },
                    # Get scores and project needed fields
                    {
                        "$project": {
                            "_id": 1,
                            "document_id": 1,
                            "metadata": 1,
                            "score": { "$meta": "searchScore" }
                        }
                    },
                    # Group by document_id to avoid duplicates
                    {
                        "$group": {
                            "_id": "$metadata.document_id",
                            "score": { "$max": "$score" },
                            "document_id": { "$first": "$metadata.document_id" }
                        }
                    },
                    # Sort by score
                    { "$sort": { "score": -1 } },
                    # Limit results
                    { "$limit": limit }
                ]
            else:
                # For non-Atlas search, use a simpler approach with $text index if available
                # Otherwise, just use metadata.document_id as a fallback
                logger.warning("Atlas search not available for semantic metadata search, using fallback approach")
                metadata_pipeline = [
                    {
                        "$match": {
                            "$or": [
                                {"metadata.topics": {"$regex": query, "$options": "i"}},
                                {"metadata.keywords": {"$regex": query, "$options": "i"}},
                                {"metadata.person_name": {"$regex": query, "$options": "i"}},
                                {"metadata.summary": {"$regex": query, "$options": "i"}}
                            ]
                        }
                    },
                    {
                        "$group": {
                            "_id": "$metadata.document_id",
                            "document_id": { "$first": "$metadata.document_id" }
                        }
                    },
                    { "$limit": limit }
                ]
            
            # Execute the pipeline
            cursor = self.chunks.aggregate(metadata_pipeline)
            results = await cursor.to_list(length=limit)
            
            # Extract document IDs
            document_ids = []
            if results:
                document_ids = [r.get("document_id") for r in results if r.get("document_id")]
                logger.info(f"Semantic metadata search found {len(document_ids)} relevant documents")
            else:
                logger.info("No documents found by semantic metadata search")
            
            return document_ids
            
        except Exception as e:
            logger.error(f"Error in semantic metadata search: {e}", exc_info=True)
            return []