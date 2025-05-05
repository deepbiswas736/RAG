import os
import re
import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple, Set

from ...domain.services.base_query_enhancer import BaseQueryEnhancer

logger = logging.getLogger(__name__)

class AdvancedQueryEnhancer(BaseQueryEnhancer):
    """
    Advanced query enhancer that combines multiple techniques:
    1. Query expansion: Add related terms to improve recall
    2. Query reformulation: Rewrite query for better alignment with document style
    3. Hypothetical document generation: Create what an ideal answer might contain
    """
    
    def __init__(self, llm_manager=None):
        """
        Initialize the advanced query enhancer.
        
        Args:
            llm_manager: Optional LLM manager for LLM-based enhancements
        """
        super().__init__(name="advanced-multi-technique")
        self.llm_manager = llm_manager
        self.expansion_enabled = os.getenv("QUERY_EXPANSION_ENABLED", "true").lower() == "true"
        self.reformulation_enabled = os.getenv("QUERY_REFORMULATION_ENABLED", "true").lower() == "true"
        self.hypothetical_enabled = os.getenv("QUERY_HYPOTHETICAL_ENABLED", "false").lower() == "true"
        
        # Domain-specific synonyms and related terms for expansion
        # This could be loaded from a file or database in a production system
        self.domain_terms = {
            "ai": ["artificial intelligence", "machine learning", "neural networks", "deep learning"],
            "ml": ["machine learning", "predictive modeling", "statistical learning"],
            "nlp": ["natural language processing", "text analysis", "language understanding"],
            "database": ["data store", "data repository", "data warehouse", "persistence layer"],
            "api": ["interface", "endpoint", "service", "REST", "GraphQL"],
            "user": ["client", "customer", "end user", "stakeholder"]
        }
        
    async def _process_query(self, query: str, **kwargs) -> str:
        """
        Process a query using multiple enhancement techniques.
        
        Args:
            query: Original query
            **kwargs: Additional parameters
            
        Returns:
            Enhanced query
        """
        enhanced_query = query
        expansion_terms = set()
        
        # Chain enhancements based on configuration
        if self.expansion_enabled:
            enhanced_query, terms = await self._expand_query(enhanced_query)
            expansion_terms.update(terms)
            
        if self.reformulation_enabled and self.llm_manager:
            enhanced_query = await self._reformulate_query(enhanced_query)
            
        if self.hypothetical_enabled and self.llm_manager:
            enhanced_query = await self._generate_hypothetical_document_query(enhanced_query)
            
        # Store expansion terms for metadata
        self.last_expansion_terms = list(expansion_terms)
        
        logger.info(f"Enhanced query: '{query}' -> '{enhanced_query}'")
        return enhanced_query
        
    async def _expand_query(self, query: str) -> Tuple[str, Set[str]]:
        """
        Expand query with related terms.
        
        Args:
            query: Original query
            
        Returns:
            Tuple of (expanded query, set of expansion terms)
        """
        expansion_terms = set()
        
        # Find terms to expand
        query_terms = set(re.findall(r'\b\w+\b', query.lower()))
        
        # Add domain-specific expansions
        for term, expansions in self.domain_terms.items():
            if term in query_terms:
                expansion_terms.update(expansions)
        
        # Don't add terms already in the query
        expansion_terms = expansion_terms - query_terms
        
        # Limit number of expansion terms to avoid query drift
        expansion_terms = set(list(expansion_terms)[:3])
        
        if not expansion_terms:
            return query, set()
            
        # Combine original query with expansion terms
        expanded_query = f"{query} {' '.join(expansion_terms)}"
        return expanded_query, expansion_terms
        
    async def _reformulate_query(self, query: str) -> str:
        """
        Reformulate the query using LLM to better match document style.
        
        Args:
            query: Original or expanded query
            
        Returns:
            Reformulated query
        """
        if not self.llm_manager:
            return query
            
        try:
            prompt = f"""Reformulate this search query to improve document retrieval without changing its meaning.
Make it more precise and use formal language that would match technical documentation.
Don't add new questions or requirements not in the original query.
Original query: "{query}"
Reformulated query:"""

            response = await self.llm_manager.generate_text(prompt, temperature=0.3, max_tokens=100)
            
            if response:
                # Clean and validate the response
                reformulated = response.strip().strip('"').strip()
                
                # Guard against completely different queries or very short responses
                if len(reformulated) < 5 or len(reformulated) > len(query) * 3:
                    return query
                    
                return reformulated
            return query
        except Exception as e:
            logger.error(f"Error in query reformulation: {e}")
            return query
            
    async def _generate_hypothetical_document_query(self, query: str) -> str:
        """
        Generate a hypothetical document query (HDQ) - describing what an ideal document
        answering the query might contain. This helps match relevant documents.
        
        Args:
            query: Original query
            
        Returns:
            Hypothetical document query
        """
        if not self.llm_manager:
            return query
            
        try:
            prompt = f"""For the search query below, write a paragraph that would appear in an ideal document that perfectly answers this query.
Focus on key technical terms, concepts, and information that would be expected in a relevant document.
Query: "{query}"
Ideal document excerpt:"""

            response = await self.llm_manager.generate_text(prompt, temperature=0.4, max_tokens=200)
            
            if response and len(response) > len(query):
                return response.strip()
            return query
        except Exception as e:
            logger.error(f"Error in hypothetical document generation: {e}")
            return query