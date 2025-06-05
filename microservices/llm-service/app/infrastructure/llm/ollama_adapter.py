"""
Ollama Integration
----------------
Implementation of LLM services using Ollama
"""

import os
import json
import time
import logging
import httpx
from typing import List, Dict, Any, Optional, AsyncGenerator
from ...domain.interfaces.llm_services import TextGenerationService, EmbeddingService
from ...domain.models.generation import GenerationResponse, StreamingChunk
from ...domain.models.embedding import Embedding
from ..resilience.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)

class OllamaTextGeneration(TextGenerationService):
    """Text generation service implementation using Ollama"""
    def __init__(self):
        """Initialize the Ollama text generation service"""
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
        self.default_model = os.getenv("OLLAMA_DEFAULT_MODEL", "phi")
        self.request_timeout = float(os.getenv("OLLAMA_TIMEOUT", "30.0"))
        self.fallback_mode = False
        
        # Initialize circuit breaker for resilience
        failure_threshold = int(os.getenv("LLM_CIRCUIT_FAILURE_THRESHOLD", "5"))
        reset_timeout = int(os.getenv("LLM_CIRCUIT_RESET_TIMEOUT", "300"))
        half_open_timeout = int(os.getenv("LLM_CIRCUIT_HALF_OPEN_TIMEOUT", "60"))
        
        self.circuit_breaker = CircuitBreaker(
            name="ollama-generation",
            failure_threshold=failure_threshold, 
            reset_timeout=reset_timeout,
            half_open_timeout=half_open_timeout
        )
        
        logger.info(f"Initialized Ollama text generation service with URL: {self.base_url} and model: {self.default_model}")

    async def check_availability(self) -> bool:
        """Check if Ollama service is available"""
        try:
            async with httpx.AsyncClient() as client:
                # Try to list models - this should work if Ollama is online
                response = await client.get(
                    f"{self.base_url}/api/tags",
                    timeout=5.0
                )
                if response.status_code == 200:
                    models = [model["name"] for model in response.json().get("models", [])]
                    logger.info(f"Ollama service is available. Available models: {', '.join(models)}")
                    self.fallback_mode = False
                    return True
                else:
                    logger.warning(f"Ollama service returned status code {response.status_code}")
                    self.fallback_mode = True
                    return False
        except Exception as e:
            logger.error(f"Error checking Ollama service: {e}")
            self.fallback_mode = True
            return False
    
    async def generate_text(self, 
                           prompt: str, 
                           model: Optional[str] = None,
                           temperature: Optional[float] = None,
                           max_tokens: Optional[int] = None,
                           system_message: Optional[str] = None) -> GenerationResponse:
        """Generate text using Ollama"""
        if self.fallback_mode:
            return self._get_fallback_response(prompt, model or self.default_model)
        
        model = model or self.default_model
        
        try:
            return await self.circuit_breaker.execute(
                self._generate_text_internal, 
                prompt, model, temperature, max_tokens, system_message
            )
        except Exception as e:
            logger.error(f"Error generating text: {e}")
            return self._get_fallback_response(prompt, model)
    
    async def _generate_text_internal(self, 
                                    prompt: str, 
                                    model: str,
                                    temperature: Optional[float],
                                    max_tokens: Optional[int],
                                    system_message: Optional[str]) -> GenerationResponse:
        """Internal implementation of text generation"""
        start_time = time.time()
        
        # Prepare request payload
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False
        }
        
        if temperature is not None:
            payload["temperature"] = temperature
            
        if max_tokens is not None:
            payload["num_predict"] = max_tokens
            
        if system_message is not None:
            payload["system"] = system_message
            
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.request_timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                elapsed_time = time.time() - start_time
                
                # Extract token counts if available
                prompt_tokens = result.get("prompt_eval_count", 0)
                completion_tokens = result.get("eval_count", 0)
                total_tokens = prompt_tokens + completion_tokens
                
                return GenerationResponse(
                    text=result["response"],
                    model=model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    elapsed_time=elapsed_time
                )
            else:
                logger.error(f"Ollama request failed with status {response.status_code}: {response.text}")
                raise Exception(f"Ollama request failed with status {response.status_code}")
    
    async def generate_streaming(self, 
                               prompt: str,
                               model: Optional[str] = None,
                               temperature: Optional[float] = None,
                               max_tokens: Optional[int] = None,
                               system_message: Optional[str] = None) -> AsyncGenerator[StreamingChunk, None]:
        """Generate streaming text using Ollama"""
        if self.fallback_mode:
            yield StreamingChunk(
                text=f"Error: Ollama service is currently unavailable. Please try again later.",
                model=model or self.default_model,
                is_final=True
            )
            return
        
        model = model or self.default_model
        
        # Prepare request payload
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True
        }
        
        if temperature is not None:
            payload["temperature"] = temperature
            
        if max_tokens is not None:
            payload["num_predict"] = max_tokens
            
        if system_message is not None:
            payload["system"] = system_message
            
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=self.request_timeout
                ) as response:
                    if response.status_code != 200:
                        yield StreamingChunk(
                            text=f"Error: Ollama request failed with status {response.status_code}",
                            model=model,
                            is_final=True
                        )
                        return
                    
                    async for line in response.aiter_lines():
                        if line:
                            try:
                                data = json.loads(line)
                                if "response" in data:
                                    is_final = data.get("done", False)
                                    yield StreamingChunk(
                                        text=data["response"],
                                        model=model,
                                        is_final=is_final
                                    )
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            logger.error(f"Error in streaming response: {type(e).__name__}: {e}")
            yield StreamingChunk(
                text=f"Error: {str(e)}",
                model=model,
                is_final=True
            )
    
    def _get_fallback_response(self, prompt: str, model: str) -> GenerationResponse:
        """Return a fallback response when service is unavailable"""
        return GenerationResponse(
            text="I'm sorry, but the language model service is currently unavailable. Please try again later.",
            model=model,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            elapsed_time=0.0
        )


class OllamaEmbedding(EmbeddingService):
    """Embedding service implementation using Ollama"""
    def __init__(self):
        """Initialize the Ollama embedding service"""
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
        self.default_model = os.getenv("OLLAMA_EMBEDDING_MODEL", "phi")
        self.request_timeout = float(os.getenv("OLLAMA_TIMEOUT", "30.0"))
        self.fallback_mode = False
        
        # Initialize circuit breaker for resilience
        failure_threshold = int(os.getenv("LLM_CIRCUIT_FAILURE_THRESHOLD", "5"))
        reset_timeout = int(os.getenv("LLM_CIRCUIT_RESET_TIMEOUT", "300"))
        half_open_timeout = int(os.getenv("LLM_CIRCUIT_HALF_OPEN_TIMEOUT", "60"))
        
        self.circuit_breaker = CircuitBreaker(
            name="ollama-embedding",
            failure_threshold=failure_threshold, 
            reset_timeout=reset_timeout,
            half_open_timeout=half_open_timeout
        )
        
        logger.info(f"Initialized Ollama embedding service with URL: {self.base_url} and model: {self.default_model}")

    async def check_availability(self) -> bool:
        """Check if Ollama service is available"""
        try:
            async with httpx.AsyncClient() as client:
                # Try to list models - this should work if Ollama is online
                response = await client.get(
                    f"{self.base_url}/api/tags",
                    timeout=5.0
                )
                if response.status_code == 200:
                    self.fallback_mode = False
                    return True
                else:
                    logger.warning(f"Ollama service returned status code {response.status_code}")
                    self.fallback_mode = True
                    return False
        except Exception as e:
            logger.error(f"Error checking Ollama service: {e}")
            self.fallback_mode = True
            return False
    
    async def create_embedding(self, text: str, model: Optional[str] = None) -> Embedding:
        """Create an embedding for a single text"""
        if self.fallback_mode:
            raise Exception("Embedding service is not available")
        
        model = model or self.default_model
        
        try:
            return await self.circuit_breaker.execute(
                self._create_embedding_internal, text, model
            )
        except Exception as e:
            logger.error(f"Error creating embedding: {e}")
            raise
    
    async def _create_embedding_internal(self, text: str, model: str) -> Embedding:
        """Internal implementation of embedding creation"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/embeddings",
                json={
                    "model": model,
                    "prompt": text
                },
                timeout=self.request_timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                if "embedding" in result:
                    vector = result["embedding"]
                    return Embedding.create(vector=vector, model=model)
                else:
                    logger.error(f"No embedding in Ollama response: {result}")
                    raise Exception("No embedding in Ollama response")
            else:
                logger.error(f"Ollama embedding request failed with status {response.status_code}: {response.text}")
                raise Exception(f"Ollama request failed with status {response.status_code}")
    
    async def create_batch_embeddings(self, texts: List[str], model: Optional[str] = None) -> List[Embedding]:
        """Create embeddings for multiple texts"""
        model = model or self.default_model
        results = []
        
        for text in texts:
            try:
                embedding = await self.create_embedding(text, model)
                results.append(embedding)
            except Exception as e:
                logger.error(f"Error creating embedding for text: {e}")
                # Add None to maintain position consistency with input texts
                results.append(None)
        
        return results
