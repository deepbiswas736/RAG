"""
LLM Service Interfaces
-------------------
Core domain interfaces for LLM functionality
"""

import abc
from typing import List, Dict, Any, AsyncGenerator, Optional
from ..models.embedding import Embedding
from ..models.generation import GenerationResponse, StreamingChunk


class EmbeddingService(abc.ABC):
    """Interface for embedding generation services"""
    
    @abc.abstractmethod
    async def create_embedding(self, text: str, model: Optional[str] = None) -> Embedding:
        """
        Create an embedding vector for the given text
        
        Args:
            text: The text to embed
            model: Optional model name to use (defaults to service default)
            
        Returns:
            An Embedding object
        """
        pass
    
    @abc.abstractmethod
    async def create_batch_embeddings(self, texts: List[str], model: Optional[str] = None) -> List[Embedding]:
        """
        Create embeddings for a batch of texts
        
        Args:
            texts: List of texts to embed
            model: Optional model name to use (defaults to service default)
            
        Returns:
            List of Embedding objects
        """
        pass


class TextGenerationService(abc.ABC):
    """Interface for text generation services"""
    
    @abc.abstractmethod
    async def generate_text(self, 
                           prompt: str, 
                           model: Optional[str] = None,
                           temperature: Optional[float] = None,
                           max_tokens: Optional[int] = None,
                           system_message: Optional[str] = None) -> GenerationResponse:
        """
        Generate text based on the provided prompt
        
        Args:
            prompt: The prompt text
            model: Optional model to use
            temperature: Optional temperature parameter (0.0-2.0)
            max_tokens: Optional maximum tokens to generate
            system_message: Optional system message for chat models
            
        Returns:
            A GenerationResponse with the generated text and metadata
        """
        pass
    
    @abc.abstractmethod
    async def generate_streaming(self, 
                               prompt: str,
                               model: Optional[str] = None,
                               temperature: Optional[float] = None,
                               max_tokens: Optional[int] = None,
                               system_message: Optional[str] = None) -> AsyncGenerator[StreamingChunk, None]:
        """
        Stream generated text based on the provided prompt
        
        Args:
            prompt: The prompt text
            model: Optional model to use
            temperature: Optional temperature parameter (0.0-2.0)
            max_tokens: Optional maximum tokens to generate
            system_message: Optional system message for chat models
            
        Yields:
            StreamingChunk objects containing text fragments
        """
        pass
