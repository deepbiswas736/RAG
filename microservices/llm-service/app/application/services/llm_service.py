"""
LLM Service
----------
Application service for managing LLM operations
"""

import logging
from typing import List, Dict, Optional, Any, AsyncGenerator, Union
from ...domain.interfaces.llm_services import TextGenerationService, EmbeddingService
from ...domain.models.embedding import Embedding
from ...domain.models.generation import GenerationResponse, StreamingChunk

logger = logging.getLogger(__name__)


class LLMService:
    """
    Application service for managing LLM operations.
    Coordinates text generation and embedding services.
    """
    
    def __init__(
        self,
        text_generation_service: TextGenerationService,
        embedding_service: EmbeddingService
    ):
        """
        Initialize the LLM service
        
        Args:
            text_generation_service: Service for text generation
            embedding_service: Service for creating embeddings
        """
        self.text_generation_service = text_generation_service
        self.embedding_service = embedding_service
        logger.info("LLM Service initialized")
    
    async def generate_text(self,
                          prompt: str,
                          context: Optional[List[Dict[str, str]]] = None,
                          model: Optional[str] = None,
                          temperature: Optional[float] = None,
                          max_tokens: Optional[int] = None) -> Dict[str, Any]:
        """
        Generate text based on prompt and optional context
        
        Args:
            prompt: The input prompt
            context: Optional list of context items
            model: Optional model name to use
            temperature: Optional temperature parameter
            max_tokens: Optional max tokens to generate
            
        Returns:
            Dictionary with generated text and metadata
        """
        # Format context if provided
        system_message = None
        if context:
            formatted_context = self._format_context(context)
            prompt = self._create_prompt_with_context(prompt, formatted_context)
        
        # Generate the response
        response = await self.text_generation_service.generate_text(
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            system_message=system_message
        )
        
        # Return as dictionary
        result = response.to_dict()
        result["input"] = prompt
        
        return result
    
    async def generate_streaming(self,
                              prompt: str,
                              context: Optional[List[Dict[str, str]]] = None,
                              model: Optional[str] = None,
                              temperature: Optional[float] = None,
                              max_tokens: Optional[int] = None) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Generate streaming text based on prompt and optional context
        
        Args:
            prompt: The input prompt
            context: Optional list of context items
            model: Optional model name to use
            temperature: Optional temperature parameter
            max_tokens: Optional max tokens to generate
            
        Yields:
            Dictionaries with text fragments
        """
        # Format context if provided
        system_message = None
        if context:
            formatted_context = self._format_context(context)
            prompt = self._create_prompt_with_context(prompt, formatted_context)
        
        # Generate streaming response
        async for chunk in self.text_generation_service.generate_streaming(
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            system_message=system_message
        ):
            yield {
                "text": chunk.text,
                "model": chunk.model,
                "is_final": chunk.is_final
            }
    
    async def create_embedding(self, text: str, model: Optional[str] = None) -> Dict[str, Any]:
        """
        Create an embedding for the given text
        
        Args:
            text: The text to embed
            model: Optional embedding model to use
            
        Returns:
            Dictionary with embedding vector and metadata
        """
        embedding = await self.embedding_service.create_embedding(text, model)
        
        return {
            "embedding": embedding.vector,
            "dimension": embedding.dimension,
            "model": embedding.model
        }
    
    async def create_batch_embeddings(self, texts: List[str], model: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Create embeddings for multiple texts
        
        Args:
            texts: List of texts to embed
            model: Optional embedding model to use
            
        Returns:
            List of dictionaries with embedding vectors and metadata
        """
        embeddings = await self.embedding_service.create_batch_embeddings(texts, model)
        
        return [
            {
                "embedding": emb.vector if emb else None,
                "dimension": emb.dimension if emb else None,
                "model": emb.model if emb else None
            }
            for emb in embeddings
        ]
    
    def _format_context(self, context: List[Dict[str, str]]) -> str:
        """Format context items into a string"""
        return "\n\n".join([
            f"CONTENT: {item.get('content', '')}\n"
            f"SOURCE: {item.get('source', '')}"
            for item in context
        ])
    
    def _create_prompt_with_context(self, query: str, context: str) -> str:
        """Create a prompt that includes context information"""
        return f"""Use the following context to answer the question. If you cannot answer the question based on the context, acknowledge that and provide general information.

CONTEXT:
{context}

QUESTION: {query}

ANSWER:"""
