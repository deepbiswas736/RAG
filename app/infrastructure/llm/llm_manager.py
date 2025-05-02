import httpx
import os
import json
from typing import List, Dict, Optional, AsyncGenerator
import logging
from ...domain.value_objects.embedding import Embedding

logger = logging.getLogger(__name__)

class LLMManager:
    def __init__(self):
        # Get configuration from environment variables with defaults
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = os.getenv("OLLAMA_MODEL", "llama2")  # Default model
        self.request_timeout = float(os.getenv("OLLAMA_TIMEOUT", "30.0"))
        self.is_available = True  # Until proven otherwise
        self.fallback_mode = False
        logger.info(f"Initializing LLM Manager with URL: {self.base_url} and model: {self.model}")

    async def check_availability(self):
        """Check if the LLM service is available"""
        try:
            async with httpx.AsyncClient() as client:
                # Try to list models - this should work if Ollama is online
                response = await client.get(
                    f"{self.base_url}/api/tags",
                    timeout=5.0
                )
                if response.status_code == 200:
                    logger.info(f"LLM service is available. Models: {response.json()}")
                    self.is_available = True
                    return True
                else:
                    logger.warning(f"LLM service returned status code {response.status_code}")
                    self.is_available = False
                    self.fallback_mode = True
                    return False
        except Exception as e:
            logger.error(f"Error checking LLM service: {e}")
            self.is_available = False
            self.fallback_mode = True
            return False

    async def generate_response(self, query: str, context: List[Dict]) -> str:
        """Generate a response using Ollama with the provided context."""
        if self.fallback_mode:
            return self._get_fallback_response(query, context)
            
        formatted_context = self._format_context(context)
        prompt = self._create_prompt(query, formatted_context)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False
                    },
                    timeout=self.request_timeout
                )
                if response.status_code == 200:
                    result = response.json()
                    return result["response"]
                elif response.status_code == 404:
                    # API endpoint might have changed or service is not available
                    logger.error(f"API endpoint not found: {self.base_url}/api/generate")
                    self.fallback_mode = True
                    return self._get_fallback_response(query, context)
                else:
                    logger.error(f"LLM request failed with status {response.status_code}: {response.text}")
                    return f"Error: Unable to generate response from LLM. Status: {response.status_code}"
        except Exception as e:
            logger.error(f"Error generating response: {type(e).__name__}: {e}")
            self.fallback_mode = True
            return self._get_fallback_response(query, context)

    async def generate_streaming_response(self, query: str, context: List[Dict]) -> AsyncGenerator[str, None]:
        """Generate a streaming response using Ollama with the provided context."""
        if self.fallback_mode:
            yield self._get_fallback_response(query, context)
            return
            
        formatted_context = self._format_context(context)
        prompt = self._create_prompt(query, formatted_context)

        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": True
                    },
                    timeout=self.request_timeout
                ) as response:
                    if response.status_code != 200:
                        self.fallback_mode = True
                        yield self._get_fallback_response(query, context)
                        return
                        
                    async for line in response.aiter_lines():
                        if line:
                            try:
                                data = json.loads(line)
                                if "response" in data:
                                    yield data["response"]
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            logger.error(f"Error in streaming response: {type(e).__name__}: {e}")
            self.fallback_mode = True
            yield self._get_fallback_response(query, context)

    def _format_context(self, context: List[Dict]) -> str:
        """Format context into a string for the prompt."""
        return "\n".join([
            f"Content: {chunk.get('content', '')}\n"
            f"Source: {chunk.get('source', '')}\n"
            for chunk in context
        ])

    def _create_prompt(self, query: str, context: str) -> str:
        """Create the full prompt with context and query."""
        return f"""Use the following context to answer the question. If you cannot answer the question based on the context, say so.

Context:
{context}

Question: {query}

Answer:"""

    def _get_fallback_response(self, query: str, context: List[Dict]) -> str:
        """Generate a simple fallback response when LLM is unavailable"""
        sources = ", ".join(set([chunk.get('source', 'Unknown') for chunk in context]))
        return f"I found some potentially relevant information in: {sources}. However, the LLM service is currently unavailable to process your query: '{query}'. Please try again later or check the LLM service configuration."