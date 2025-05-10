"""
Query Processing Service
---------------------
Core application service for processing queries with advanced reranking
"""

import logging
import time
import math
import re
import string
from typing import List, Dict, Any, Optional, AsyncGenerator, Tuple
from datetime import datetime
from collections import Counter

from ...domain.interfaces.llm_service_client import LLMServiceClient
from ...domain.interfaces.document_service_client import DocumentServiceClient
from ...domain.interfaces.query_repository import QueryRepository
from ...domain.models.query import Query, QueryStatus
from ...domain.models.response import QueryResponse, DocumentReference
from ... import config

logger = logging.getLogger(__name__)


class QueryProcessor:
    """Core service for processing queries"""
    
    def __init__(
        self,
        llm_service_client: LLMServiceClient,
        document_service_client: DocumentServiceClient,
        query_repository: QueryRepository
    ):
        """
        Initialize the query processor
        
        Args:
            llm_service_client: Client for communicating with the LLM Service
            document_service_client: Client for communicating with the Document Service
            query_repository: Repository for storing queries and responses
        """
        self.llm_service_client = llm_service_client
        self.document_service_client = document_service_client
        self.query_repository = query_repository
        logger.info("Initialized Query Processor")
        
        # Load configuration settings
        self.enable_metadata_search = getattr(config, "ENABLE_METADATA_SEARCH", True)
        self.default_metadata_fields = getattr(config, "DEFAULT_METADATA_FIELDS", 
            ["title", "author", "keywords", "topic", "summary"])
        self.metadata_importance = getattr(config, "METADATA_IMPORTANCE", {
            "title": 0.3,
            "author": 0.1,
            "keywords": 0.2,
            "topic": 0.2,
            "summary": 0.2
        })
        
        logger.info(f"Metadata search enabled: {self.enable_metadata_search}")
    
    async def process_query(self, query: Query) -> QueryResponse:
        """
        Process a query and generate a response
        
        Args:
            query: The query to process
            
        Returns:
            The generated response
        """
        start_time = time.time()
        
        try:
            # Save the query with pending status
            query.update_status(QueryStatus.PROCESSING)
            await self.query_repository.save(query)
            
            # Search for relevant documents
            logger.info(f"Searching for documents relevant to query: {query.id.value}")
            document_chunks = await self.search_relevant_documents(
                query_text=query.text,
                filters=query.filters
            )
            
            # Generate LLM response with context
            logger.info(f"Generating response using LLM for query: {query.id.value}")
            context = self._prepare_context_from_chunks(document_chunks)
            
            # Include conversation history if available
            system_message = None
            if query.conversation_history and query.query_type.value in ["conversational", "hybrid"]:
                system_message = self._format_conversation_history(query.conversation_history)
            
            # Generate response using LLM
            llm_response = await self.llm_service_client.generate_text(
                prompt=query.text,
                context=context,
                system_message=system_message
            )
            
            # Create document references
            references = self._create_document_references(document_chunks)
            
            # Create query response
            elapsed_time = time.time() - start_time
            response = QueryResponse.create(
                query_id=query.id.value,
                text=llm_response["text"],
                references=references,
                model=llm_response.get("model"),
                latency=elapsed_time,
                token_usage=llm_response.get("tokens", {})
            )
            
            # Save the response
            await self.query_repository.save_response(response)
            
            # Update query status to completed
            query.update_status(QueryStatus.COMPLETED)
            await self.query_repository.update(query)
            
            logger.info(f"Completed processing query: {query.id.value}")
            return response
            
        except Exception as e:
            logger.error(f"Error processing query {query.id.value}: {str(e)}")
            
            # Update query status to failed
            query.update_status(QueryStatus.FAILED)
            query.metadata["error"] = str(e)
            await self.query_repository.update(query)
            
            # Create error response
            error_response = QueryResponse.create(
                query_id=query.id.value,
                text=f"Error processing your query: {str(e)}",
                model="error",
                latency=time.time() - start_time
            )
            await self.query_repository.save_response(error_response)
            
            return error_response
    
    async def process_streaming_query(self, query: Query) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process a query with streaming response
        
        Args:
            query: The query to process
            
        Yields:
            Streaming chunks of the response
        """
        start_time = time.time()
        response_chunks = []
        
        try:
            # Save the query with pending status
            query.update_status(QueryStatus.PROCESSING)
            await self.query_repository.save(query)
            
            # Search for relevant documents
            logger.info(f"Searching for documents relevant to query: {query.id.value}")
            document_chunks = await self.search_relevant_documents(
                query_text=query.text,
                filters=query.filters
            )
            
            # Generate LLM response with context
            logger.info(f"Generating streaming response for query: {query.id.value}")
            context = self._prepare_context_from_chunks(document_chunks)
            
            # Include conversation history if available
            system_message = None
            if query.conversation_history and query.query_type.value in ["conversational", "hybrid"]:
                system_message = self._format_conversation_history(query.conversation_history)
            
            # Stream response chunks
            full_text = ""
            model_name = None
            
            async for chunk in self.llm_service_client.generate_streaming(
                prompt=query.text,
                context=context,
                system_message=system_message
            ):
                # Build the full response text
                text_chunk = chunk.get("text", "")
                full_text += text_chunk
                model_name = model_name or chunk.get("model")
                
                # Keep track of chunks for response metadata
                response_chunks.append(chunk)
                
                # Yield the chunk with additional metadata
                yield {
                    "query_id": query.id.value,
                    "text": text_chunk,
                    "is_final": chunk.get("is_final", False)
                }
            
            # Create document references
            references = self._create_document_references(document_chunks)
            
            # Create final query response
            elapsed_time = time.time() - start_time
            token_usage = {}
            
            # If the LLM service provided token counts in the final chunk
            if response_chunks and "token_usage" in response_chunks[-1]:
                token_usage = response_chunks[-1]["token_usage"]
            
            response = QueryResponse.create(
                query_id=query.id.value,
                text=full_text,
                references=references,
                model=model_name,
                latency=elapsed_time,
                token_usage=token_usage
            )
            
            # Save the response
            await self.query_repository.save_response(response)
            
            # Update query status to completed
            query.update_status(QueryStatus.COMPLETED)
            await self.query_repository.update(query)
            
            logger.info(f"Completed streaming response for query: {query.id.value}")
            
        except Exception as e:
            logger.error(f"Error processing streaming query {query.id.value}: {str(e)}")
            
            # Update query status to failed
            query.update_status(QueryStatus.FAILED)
            query.metadata["error"] = str(e)
            await self.query_repository.update(query)
            
            # Yield error message as final chunk
            yield {
                "query_id": query.id.value,
                "text": f"Error: {str(e)}",
                "is_final": True,
                "is_error": True
            }
    
    async def search_relevant_documents(
        self, 
        query_text: str, 
        limit: int = 10, # Increased limit to get more candidates for reranking
        filters: Optional[Dict[str, Any]] = None,
        search_type: str = "advanced"
    ) -> List[Dict[str, Any]]:
        """
        Search for documents relevant to the query with advanced reranking
        
        Args:
            query_text: The query text
            limit: Maximum number of results to return
            filters: Optional filters to apply
            search_type: Type of search to perform (advanced, hybrid, basic)
            
        Returns:
            List of relevant document chunks, reranked for relevance
        """
        try:
            # Decide which search method to use based on query characteristics
            chunks = []
            use_server_side_ranking = search_type == "basic"
            
            # Calculate search limit with candidate multiplier
            search_limit = min(
                limit * getattr(config, "VECTOR_SEARCH_CANDIDATE_MULTIPLIER", 3), 
                getattr(config, "MAX_CANDIDATES", 30)
            )
            
            # First, try using advanced embedding search if possible
            if not use_server_side_ranking:
                try:
                    # Generate query embedding via LLM service
                    embed_response = await self.llm_service_client.generate_embeddings(query_text)
                    query_embedding = embed_response.get("embedding", [])
                    
                    if query_embedding:
                        # Determine ranking method based on query type
                        ranking_method = self._determine_ranking_method(query_text)
                        logger.info(f"Selected ranking method '{ranking_method}' for query: {query_text}")
                        
                        # Check if we should enhance with metadata search
                        if self.enable_metadata_search and search_type == "advanced":
                            # Use search with embeddings (content + metadata)
                            logger.info(f"Using search_documents_with_embeddings for query: {query_text}")
                            chunks = await self.document_service_client.search_documents_with_embeddings(
                                query_text=query_text,
                                query_embedding=query_embedding,
                                limit=search_limit,
                                filters=filters,
                                include_metadata_search=True
                            )
                        else:
                            # Use vector search with client-side ranking
                            logger.info(f"Using vector_search_with_ranking for query: {query_text}")
                            chunks = await self.document_service_client.vector_search_with_ranking(
                                query_text=query_text,
                                query_embedding=query_embedding,
                                limit=search_limit,
                                filters=filters,
                                ranking_method=ranking_method
                            )
                    else:
                        use_server_side_ranking = True
                        
                except Exception as e:
                    logger.warning(f"Error in advanced search, falling back to regular search: {str(e)}")
                    use_server_side_ranking = True
            
            # Fallback to server-side ranking if needed
            if use_server_side_ranking or not chunks:
                # Fallback to standard search + reranking
                chunks = await self.document_service_client.search_documents(
                    query_text=query_text,
                    limit=search_limit,
                    filters=filters
                )
                
                # Apply reranking if we have enough chunks
                if len(chunks) > 1:
                    logger.info(f"Reranking {len(chunks)} document chunks for query: {query_text}")
                    chunks = self._rerank_chunks(query_text, chunks)
            
            # Keep only the top results after searching/reranking
            chunks = chunks[:limit]
            
            logger.info(f"Returning {len(chunks)} document chunks for query: {query_text}")
            return chunks
        except Exception as e:
            logger.error(f"Error searching documents: {str(e)}")
            return []
            
    def _determine_ranking_method(self, query_text: str) -> str:
        """
        Determine the best ranking method based on the query
        
        Args:
            query_text: The query text to analyze
            
        Returns:
            The name of the ranking method to use
        """
        query_lower = query_text.lower()
        
        # Determine if query is metadata-focused
        metadata_keywords = ["about", "topic", "author", "written by", "title", "category",
                           "subject", "related to", "field of", "published", "summary of"]
                           
        # Check if query contains metadata-focused terms
        if any(keyword in query_lower for keyword in metadata_keywords):
            return "metadata_focus"
            
        # Check if query is keyword-focused (specific terms, definitions)
        keyword_indicators = ["definition of", "what is", "meaning of", "describe", "explain", 
                            "how to", "what are", "steps to", "examples of"]
                            
        if any(indicator in query_lower for indicator in keyword_indicators):
            return "keyword_boost"
            
        # Default to hybrid for balanced queries
        return "hybrid"

    def _rerank_chunks(self, query: str, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Rerank document chunks based on multiple relevance factors
        
        Args:
            query: The original user query
            chunks: List of document chunks with scores
            
        Returns:
            Reranked list of document chunks
        """
        # Extract query terms for keyword analysis
        query_terms = self._extract_terms(query.lower())
        
        for chunk in chunks:
            original_score = chunk.get("score", 0)
            content = chunk.get("content", "").lower()
            metadata = chunk.get("metadata", {})
            
            # Initialize the composite score components
            keyword_score = self._calculate_keyword_score(content, query_terms)
            recency_score = self._calculate_recency_score(metadata)
            authority_score = self._calculate_authority_score(metadata)
            length_penalty = self._calculate_length_penalty(content)
            metadata_score = self._calculate_metadata_score(metadata, query_terms)
            
            # Get ranking weights based on query type
            ranking_method = self._determine_ranking_method(query)
            weights = getattr(config, "VECTOR_WEIGHTS", {}).get(ranking_method, {
                "vector_similarity": 0.6,
                "keyword_match": 0.15,
                "position_score": 0.1,
                "metadata_score": 0.15
            })
            
            # Compute composite score using configurable weights
            composite_score = (
                original_score * weights["vector_similarity"] +
                keyword_score * weights["keyword_match"] +
                metadata_score * weights["metadata_score"] +
                (recency_score * 0.05 + 
                authority_score * 0.05 + 
                length_penalty * 0.05) * weights["position_score"]
            )
            
            # Store both scores for comparison/debugging
            chunk["original_score"] = original_score
            chunk["score"] = composite_score
            
            # Add score components for transparency
            chunk["score_components"] = {
                "vector_similarity": original_score,
                "keyword_relevance": keyword_score,
                "metadata_score": metadata_score,
                "recency": recency_score,
                "authority": authority_score,
                "length_penalty": length_penalty
            }
        
        # Sort by composite score (descending)
        return sorted(chunks, key=lambda x: x.get("score", 0), reverse=True)
        
    def _calculate_metadata_score(self, metadata: Dict[str, Any], query_terms: List[str]) -> float:
        """
        Calculate relevance score based on metadata matching
        
        Args:
            metadata: Document metadata
            query_terms: List of query terms
            
        Returns:
            Metadata relevance score (0.0 to 1.0)
        """
        if not metadata:
            return 0.0
            
        score = 0.0
        total_weight = 0.0
        
        # Process each metadata field based on importance
        for field, importance in self.metadata_importance.items():
            if field in metadata and metadata[field]:
                # Get field value and convert to string if needed
                field_value = str(metadata[field]).lower()
                
                # Calculate term overlap
                field_terms = self._extract_terms(field_value)
                matching_terms = sum(1 for term in query_terms if term in field_terms)
                field_score = matching_terms / max(len(query_terms), 1) if query_terms else 0
                
                # Add weighted score
                score += field_score * importance
                total_weight += importance
        
        # Normalize score if we have weights
        if total_weight > 0:
            score /= total_weight
            
        return score

    def _extract_terms(self, text: str) -> List[str]:
        """Extract meaningful terms from text for keyword analysis"""
        # Remove punctuation and split into words
        text = text.translate(str.maketrans("", "", string.punctuation))
        words = text.split()
        
        # Filter out common stopwords (simplified list)
        stopwords = {"a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "with", "by", "about", "is", 
                    "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did", "of", "from"}
        return [word for word in words if word not in stopwords and len(word) > 1]
    
    def _calculate_keyword_score(self, content: str, query_terms: List[str]) -> float:
        """Calculate keyword match score based on term frequency"""
        if not query_terms:
            return 0.5  # Neutral score if no meaningful query terms
            
        content_lower = content.lower()
        content_terms = self._extract_terms(content_lower)
        
        if not content_terms:
            return 0.0
            
        # Count occurrences of query terms in content
        term_counts = Counter(content_terms)
        
        # Calculate term frequency score (normalized by content length)
        matches = sum(term_counts[term] for term in query_terms if term in term_counts)
        total_terms = sum(term_counts.values())
        
        # Term frequency normalized for document length
        tf_score = matches / total_terms if total_terms > 0 else 0
        
        # Calculate term presence score (what percentage of query terms appear?)
        presence_count = sum(1 for term in query_terms if term in content_lower)
        presence_score = presence_count / len(query_terms) if query_terms else 0
        
        # Combine scores (term frequency + term presence)
        return (tf_score * 0.5) + (presence_score * 0.5)
    
    def _calculate_recency_score(self, metadata: Dict[str, Any]) -> float:
        """Calculate recency score based on document creation/update date"""
        # Default to neutral score if no date information
        if not metadata:
            return 0.5
            
        # Look for date fields in metadata
        date_str = metadata.get("modified_date") or metadata.get("created_date")
        
        if not date_str:
            return 0.5
            
        try:
            # Parse the date string
            if isinstance(date_str, str):
                date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            elif isinstance(date_str, datetime):
                date_obj = date_str
            else:
                return 0.5
                
            # Calculate age in days
            now = datetime.now()
            age_days = (now - date_obj).days
            
            # Apply decay function (exponential decay with half-life of 180 days)
            # More recent documents get higher scores
            half_life = 180  # days
            decay = math.exp(-0.693 * age_days / half_life)
            
            return decay
        except Exception:
            return 0.5
    
    def _calculate_authority_score(self, metadata: Dict[str, Any]) -> float:
        """
        Calculate authority score based on document source
        This is a placeholder for a more sophisticated source authority system
        """
        # Default to neutral score
        if not metadata:
            return 0.5
            
        # Source domain authority (could be loaded from a configuration)
        source = metadata.get("source_path", "").lower()
        
        # Example domain authority scoring - replace with actual domain authority data
        if source:
            if "official" in source or "gov" in source:
                return 0.9  # Government or official sources
            elif "research" in source or "edu" in source:
                return 0.8  # Research or educational sources
            elif "news" in source:
                return 0.7  # News sources
            
        # Author authority could also be factored in here
        # if metadata.get("author") in known_experts: return high_score
        
        return 0.5  # Neutral score for unknown sources
    
    def _calculate_length_penalty(self, content: str) -> float:
        """
        Calculate length penalty to balance between too short and too long chunks
        Short chunks might lack context, very long chunks might be less focused
        """
        # Count words in content
        word_count = len(content.split())
        
        # Ideal length range: 100-500 words
        if 100 <= word_count <= 500:
            return 1.0  # Optimal length
        elif word_count < 100:
            # Penalty increases as length decreases below 100
            return max(0.5, word_count / 100)
        else:
            # Penalty increases as length increases above 500
            # 500 words: score = 1.0
            # 1000 words: score = 0.5
            # 1500+ words: score = 0.3
            return max(0.3, 1.0 - (word_count - 500) / 1000)
    
    def _prepare_context_from_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """
        Prepare context from document chunks for the LLM
        
        Args:
            chunks: List of document chunks
            
        Returns:
            Context formatted for the LLM Service
        """
        context = []
        
        for chunk in chunks:
            content = chunk.get("content", "")
            source = f"{chunk.get('document_id', 'unknown')}"
            
            if "metadata" in chunk:
                metadata = chunk["metadata"]
                if "title" in metadata:
                    source += f" - {metadata['title']}"
                if "page" in metadata:
                    source += f" (page {metadata['page']})"
            
            context.append({
                "content": content,
                "source": source
            })
        
        return context
    
    def _create_document_references(self, chunks: List[Dict[str, Any]]) -> List[DocumentReference]:
        """
        Create document references from document chunks
        
        Args:
            chunks: List of document chunks
            
        Returns:
            List of document references
        """
        references = []
        
        for chunk in chunks:
            document_id = chunk.get("document_id", "unknown")
            metadata = chunk.get("metadata", {})
            
            reference = DocumentReference(
                document_id=document_id,
                title=metadata.get("title"),
                source=metadata.get("source_path"),
                page=metadata.get("page"),
                metadata=metadata,
                relevance_score=chunk.get("score"),
                content_excerpt=chunk.get("content", "")[:200] + "..."  # First 200 chars
            )
            
            references.append(reference)
        
        return references
    
    def _format_conversation_history(self, conversation_history: List[Dict[str, Any]]) -> str:
        """
        Format conversation history as system message
        
        Args:
            conversation_history: List of conversation turns
            
        Returns:
            Formatted conversation history
        """
        history_text = "Conversation history:\n\n"
        
        for turn in conversation_history:
            if "user" in turn:
                history_text += f"User: {turn['user']}\n"
            if "assistant" in turn:
                history_text += f"Assistant: {turn['assistant']}\n"
            history_text += "\n"
        
        return history_text
