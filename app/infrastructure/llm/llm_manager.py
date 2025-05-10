import httpx
import os
import json
from typing import List, Dict, Optional, AsyncGenerator
import logging
from ...domain.value_objects.embedding import Embedding
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class CircuitBreaker:
    """
    Circuit breaker pattern implementation to protect LLM service from being overwhelmed.
    Prevents cascading failures by failing fast when the service is experiencing issues.
    """
    
    def __init__(
        self, 
        failure_threshold: int = 5,
        reset_timeout: int = 60,
        half_open_timeout: int = 30
    ):
        """
        Initialize the circuit breaker.
        
        Args:
            failure_threshold: Number of failures before circuit opens
            reset_timeout: Seconds to wait before attempting to close circuit
            half_open_timeout: Seconds to wait in half-open state
        """
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.half_open_timeout = half_open_timeout
        
        # Circuit state
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed (normal), open (failing), half-open (testing)
        self.last_state_change = datetime.now()
        
        logger.info(f"Circuit breaker initialized with threshold: {failure_threshold}, reset: {reset_timeout}s")
    
    async def execute(self, func, *args, **kwargs):
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Async function to execute
            *args, **kwargs: Arguments to pass to the function
            
        Returns:
            Function result
            
        Raises:
            Exception if circuit is open or function fails
        """
        # Check circuit state
        current_state = self._check_state()
        
        if current_state == "open":
            logger.warning("Circuit is open, failing fast")
            raise Exception("Circuit breaker is open, LLM service is unavailable")
            
        try:
            result = await func(*args, **kwargs)
            
            # Success, reset circuit if it was half-open
            if current_state == "half-open":
                logger.info("Successful call in half-open state, closing circuit")
                self._close_circuit()
                
            return result
            
        except Exception as e:
            # Track failure
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            
            # Check if we should open the circuit
            if current_state == "closed" and self.failure_count >= self.failure_threshold:
                logger.warning(f"Failure threshold reached ({self.failure_count}), opening circuit")
                self._open_circuit()
            
            # Propagate the original error
            raise e
    
    def _check_state(self) -> str:
        """
        Check and update circuit state based on timeouts.
        
        Returns:
            Current circuit state
        """
        now = datetime.now()
        
        if self.state == "open" and self.last_state_change + timedelta(seconds=self.reset_timeout) < now:
            # Time to try half-open state
            logger.info(f"Circuit reset timeout reached ({self.reset_timeout}s), switching to half-open")
            self.state = "half-open"
            self.last_state_change = now
            
        elif self.state == "half-open" and self.last_state_change + timedelta(seconds=self.half_open_timeout) < now:
            # Half-open timed out without success, go back to open
            logger.warning(f"Half-open timeout reached ({self.half_open_timeout}s), reopening circuit")
            self._open_circuit()
            
        return self.state
    
    def _open_circuit(self):
        """Set circuit to open state."""
        self.state = "open"
        self.last_state_change = datetime.now()
        
    def _close_circuit(self):
        """Reset circuit to closed state."""
        self.state = "closed"
        self.failure_count = 0
        self.last_failure_time = None
        self.last_state_change = datetime.now()


class LLMManager:
    def __init__(self):
        # Get configuration from environment variables with defaults
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = os.getenv("OLLAMA_MODEL", "llama2")  # Default model
        self.request_timeout = float(os.getenv("OLLAMA_TIMEOUT", "30.0"))
        self.is_available = True  # Until proven otherwise
        self.fallback_mode = False
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=int(os.getenv("LLM_CIRCUIT_FAILURE_THRESHOLD", "5")),
            reset_timeout=int(os.getenv("LLM_CIRCUIT_RESET_TIMEOUT", "300")),  # 5 minutes
            half_open_timeout=int(os.getenv("LLM_CIRCUIT_HALF_OPEN_TIMEOUT", "60"))  # 1 minute
        )
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
            return await self.circuit_breaker.execute(
                self._generate_response_internal, prompt, context
            )
        except Exception as e:
            logger.error(f"Error generating LLM response: {e}")
            return f"Error: Unable to generate response. The LLM service may be temporarily unavailable. ({str(e)})"

    async def _generate_response_internal(self, prompt: str, context: List[Dict]) -> str:
        """Internal implementation of response generation."""
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

    async def generate_summary(self, summary_prompt: str) -> str:
        """Generate a summary response based on the provided summary prompt.
        This is used specifically for combining individual chunk responses."""
        if self.fallback_mode:
            return f"Unable to generate summary: LLM service is in fallback mode."
            
        try:
            return await self.circuit_breaker.execute(
                self._generate_summary_internal, summary_prompt
            )
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return f"Error: Unable to generate summary. The LLM service may be temporarily unavailable. ({str(e)})"

    async def _generate_summary_internal(self, summary_prompt: str) -> str:
        """Internal implementation of summary generation."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": summary_prompt,
                    "stream": False
                },
                timeout=self.request_timeout
            )
            if response.status_code == 200:
                result = response.json()
                return result["response"]
            elif response.status_code == 404:
                logger.error(f"API endpoint not found: {self.base_url}/api/generate")
                self.fallback_mode = True
                return "Error: Unable to generate summary. LLM service API endpoint not found."
            else:
                logger.error(f"LLM request failed with status {response.status_code}: {response.text}")
                return f"Error: Unable to generate summary from LLM. Status: {response.status_code}"

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