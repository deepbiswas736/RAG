"""
HTTP LLM Service Client
---------------------
Implementation of the LLM Service client using HTTP
"""

import os
import json
import logging
import httpx
from typing import List, Dict, Any, Optional, AsyncGenerator
from ...domain.interfaces.llm_service_client import LLMServiceClient

logger = logging.getLogger(__name__)


class HttpLLMServiceClient(LLMServiceClient):
    """HTTP client for the LLM Service"""
    
    def __init__(self, base_url: Optional[str] = None):
        """
        Initialize the LLM Service client
        
        Args:
            base_url: Optional base URL for the LLM Service (default: environment variable)
        """
        self.base_url = base_url or os.environ.get("LLM_SERVICE_URL", "http://llm-service:8001")
        self.timeout = float(os.environ.get("LLM_SERVICE_TIMEOUT", "30.0"))
        logger.info(f"Initialized LLM Service client with URL: {self.base_url}")
    
    async def generate_text(self, 
                          prompt: str, 
                          context: Optional[List[Dict[str, str]]] = None,
                          model: Optional[str] = None,
                          temperature: Optional[float] = None,
                          max_tokens: Optional[int] = None,
                          system_message: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate text using the LLM Service
        """
        payload = {
            "prompt": prompt
        }
        
        if context is not None:
            payload["context"] = context
            
        if model is not None:
            payload["model"] = model
            
        if temperature is not None:
            payload["temperature"] = temperature
            
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
            
        if system_message is not None:
            payload["system_message"] = system_message
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/llm/generate",
                    json=payload,
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    error_message = f"LLM Service error: {response.status_code} - {response.text}"
                    logger.error(error_message)
                    raise Exception(error_message)
        except Exception as e:
            logger.error(f"Error communicating with LLM Service: {str(e)}")
            raise
    
    async def generate_embeddings(self, text: str, model: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate embeddings for a text using the LLM Service
        
        Args:
            text: The text to generate an embedding for
            model: Optional embedding model to use
            
        Returns:
            Dictionary containing the embedding and metadata
        """
        payload = {
            "text": text
        }
        
        if model is not None:
            payload["model"] = model
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/embeddings/create",
                    json=payload,
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    error_message = f"LLM Service embedding error: {response.status_code} - {response.text}"
                    logger.error(error_message)
                    raise Exception(error_message)
        except Exception as e:
            logger.error(f"Error generating embeddings with LLM Service: {str(e)}")
            raise
            
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
        # Filter metadata by specified fields if provided
        if fields:
            metadata_text = " ".join(str(metadata.get(field, "")) for field in fields)
        else:
            # Use all metadata fields
            metadata_text = " ".join(str(value) for value in metadata.values())
        
        # Normalize metadata text
        metadata_text = metadata_text.strip()
        if not metadata_text:
            logger.warning("Empty metadata text for embedding generation")
            metadata_text = "empty metadata"
        
        # Generate embedding for the metadata text
        payload = {
            "text": metadata_text
        }
        
        if model is not None:
            payload["model"] = model
            
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/embeddings/create",
                    json=payload,
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    result = response.json()
                    # Add metadata fields used for transparency
                    result["metadata_fields"] = fields if fields else list(metadata.keys())
                    return result
                else:
                    error_message = f"LLM Service metadata embedding error: {response.status_code} - {response.text}"
                    logger.error(error_message)
                    raise Exception(error_message)
        except Exception as e:
            logger.error(f"Error generating metadata embeddings with LLM Service: {str(e)}")
            raise
    
    async def generate_streaming(self, 
                               prompt: str,
                               context: Optional[List[Dict[str, str]]] = None,
                               model: Optional[str] = None,
                               temperature: Optional[float] = None,
                               max_tokens: Optional[int] = None,
                               system_message: Optional[str] = None) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Generate streaming text using the LLM Service
        """
        payload = {
            "prompt": prompt
        }
        
        if context is not None:
            payload["context"] = context
            
        if model is not None:
            payload["model"] = model
            
        if temperature is not None:
            payload["temperature"] = temperature
            
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
            
        if system_message is not None:
            payload["system_message"] = system_message
        
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/llm/stream",
                    json=payload,
                    timeout=self.timeout
                ) as response:
                    if response.status_code != 200:
                        error_message = f"LLM Service error: {response.status_code}"
                        logger.error(error_message)
                        raise Exception(error_message)
                    
                    async for line in response.aiter_lines():
                        if line.strip():
                            try:
                                yield json.loads(line)
                            except json.JSONDecodeError as e:
                                logger.error(f"Error parsing streaming response: {e}")
        except Exception as e:
            logger.error(f"Error in streaming from LLM Service: {str(e)}")
            raise
    
    async def create_embedding(self, 
                             text: str,
                             model: Optional[str] = None) -> Dict[str, Any]:
        """
        Create an embedding using the LLM Service
        """
        payload = {
            "text": text
        }
        
        if model is not None:
            payload["model"] = model
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/llm/embeddings",
                    json=payload,
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    error_message = f"LLM Service error: {response.status_code} - {response.text}"
                    logger.error(error_message)
                    raise Exception(error_message)
        except Exception as e:
            logger.error(f"Error communicating with LLM Service: {str(e)}")
            raise
    
    async def create_batch_embeddings(self, 
                                    texts: List[str],
                                    model: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Create batch embeddings using the LLM Service
        """
        payload = {
            "texts": texts
        }
        
        if model is not None:
            payload["model"] = model
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/llm/batch_embeddings",
                    json=payload,
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    error_message = f"LLM Service error: {response.status_code} - {response.text}"
                    logger.error(error_message)
                    raise Exception(error_message)
        except Exception as e:
            logger.error(f"Error communicating with LLM Service: {str(e)}")
            raise
    
    async def check_health(self) -> Dict[str, Any]:
        """
        Check the health of the LLM Service
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/health",
                    timeout=5.0  # Short timeout for health checks
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    return {"status": "unhealthy", "message": f"Status code: {response.status_code}"}
        except Exception as e:
            logger.error(f"Error checking LLM Service health: {str(e)}")
            return {"status": "unhealthy", "message": str(e)}
