"""
LLM Service Client Interface
--------------------------
Interface for communicating with the LLM Service microservice
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncGenerator


class LLMServiceClient(ABC):
    """Client interface for LLM Service"""
    
    @abstractmethod
    async def generate_text(self, 
                          prompt: str, 
                          context: Optional[List[Dict[str, str]]] = None,
                          model: Optional[str] = None,
                          temperature: Optional[float] = None,
                          max_tokens: Optional[int] = None,
                          system_message: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate text using the LLM Service
        
        Args:
            prompt: The prompt to generate text from
            context: Optional list of context items with content and source
            model: Optional model to use
            temperature: Optional temperature setting
            max_tokens: Optional maximum tokens to generate
            system_message: Optional system message
            
        Returns:
            Response containing generated text and metadata
        """
        pass
    
    @abstractmethod
    async def generate_streaming(self, 
                               prompt: str,
                               context: Optional[List[Dict[str, str]]] = None,
                               model: Optional[str] = None,
                               temperature: Optional[float] = None,
                               max_tokens: Optional[int] = None,
                               system_message: Optional[str] = None) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Generate streaming text using the LLM Service
        
        Args:
            prompt: The prompt to generate text from
            context: Optional list of context items with content and source
            model: Optional model to use
            temperature: Optional temperature setting
            max_tokens: Optional maximum tokens to generate
            system_message: Optional system message
            
        Yields:
            Stream of response chunks containing generated text and metadata
        """
        pass
    
    @abstractmethod
    async def generate_embeddings(self, 
                                text: str,
                                model: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate embeddings for text using the LLM Service
        
        Args:
            text: The text to generate embeddings for
            model: Optional embedding model to use
            
        Returns:
            Dictionary containing embedding vector and metadata
        """
        pass
        
    @abstractmethod
    async def generate_metadata_embeddings(self, 
                                        metadata: Dict[str, Any], 
                                        fields: Optional[List[str]] = None,
                                        model: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate embeddings for document metadata using the LLM Service
        
        Args:
            metadata: The metadata dictionary to generate embeddings for
            fields: Optional list of metadata fields to include (default: all)
            model: Optional embedding model to use
            
        Returns:
            Dictionary containing the embedding and metadata
        """
        pass
    
    @abstractmethod
    async def create_embedding(self, 
                             text: str,
                             model: Optional[str] = None) -> Dict[str, Any]:
        """
        Create an embedding using the LLM Service
        
        Args:
            text: The text to create an embedding for
            model: Optional model to use
            
        Returns:
            Response containing the embedding vector and metadata
        """
        pass
    
    @abstractmethod
    async def create_batch_embeddings(self, 
                                    texts: List[str],
                                    model: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Create batch embeddings using the LLM Service
        
        Args:
            texts: List of texts to create embeddings for
            model: Optional model to use
            
        Returns:
            List of responses containing embedding vectors and metadata
        """
        pass
    
    @abstractmethod
    async def check_health(self) -> Dict[str, Any]:
        """
        Check the health of the LLM Service
        
        Returns:
            Health status information
        """
        pass
