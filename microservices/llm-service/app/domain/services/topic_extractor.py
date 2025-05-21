"""
Topic Extractor
-------------
Service to extract topics from document chunks
"""

import logging
import re
import json
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class TopicExtractor:
    """Service for extracting topics from document chunks"""
    
    def __init__(self, llm_service):
        """
        Initialize the Topic Extractor
        
        Args:
            llm_service: LLM service for text generation
        """
        self.llm_service = llm_service
        
    async def extract_chunk_topics(self, chunk_content: str, max_topics: int = 5, max_tokens: int = 100) -> List[str]:
        """
        Extract topics from a document chunk
        
        Args:
            chunk_content: Text content of the chunk
            max_topics: Maximum number of topics to extract
            max_tokens: Maximum tokens for LLM response
            
        Returns:
            List of topic strings
        """
        if not chunk_content or not chunk_content.strip():
            logger.warning("Cannot extract topics from empty chunk content")
            return []
            
        # Create topic extraction prompt
        topic_prompt = self._create_topic_extraction_prompt(chunk_content, max_topics)
        
        # Extract topics using LLM
        try:
            topics_text = await self.llm_service.generate_text(
                prompt=topic_prompt,
                temperature=0.5,  # Higher temperature for more diverse topics
                max_tokens=max_tokens
            )
            
            # Parse topics from LLM response
            topics = self._parse_topics_from_llm_output(topics_text)
            logger.info(f"Extracted {len(topics)} topics from chunk: {topics}")
            return topics
            
        except Exception as e:
            logger.error(f"Error extracting topics from chunk: {e}")
            return []
    
    async def extract_topics_batch(self, chunks: List[Dict[str, Any]], 
                                 content_key: str = "content",
                                 max_topics: int = 5,
                                 max_tokens: int = 100) -> Dict[str, List[str]]:
        """
        Extract topics from multiple chunks in a batch
        
        Args:
            chunks: List of chunk dictionaries
            content_key: Key to access content in chunk dictionaries
            max_topics: Maximum number of topics to extract per chunk
            max_tokens: Maximum tokens for LLM response
            
        Returns:
            Dictionary mapping chunk_id to list of topics
        """
        results = {}
        
        for chunk in chunks:
            chunk_id = chunk.get("chunk_id")
            if not chunk_id:
                logger.warning(f"Skipping chunk with no chunk_id")
                continue
                
            content = chunk.get(content_key)
            if not content:
                logger.warning(f"Skipping chunk {chunk_id} with no content")
                results[chunk_id] = []
                continue
                
            try:
                topics = await self.extract_chunk_topics(content, max_topics, max_tokens)
                results[chunk_id] = topics
            except Exception as e:
                logger.error(f"Error extracting topics for chunk {chunk_id}: {e}")
                results[chunk_id] = []
                
        return results
    
    def _create_topic_extraction_prompt(self, chunk_content: str, max_topics: int = 5) -> str:
        """
        Create a prompt for extracting topics from a text chunk
        
        Args:
            chunk_content: Text content of the chunk
            max_topics: Maximum number of topics to extract
            
        Returns:
            Prompt text for LLM
        """
        # Limit content length for the prompt
        preview_content = chunk_content[:1500]

        return f"""Identify the main topics discussed in the following text chunk.
List up to {max_topics} key topics as a JSON list of strings.
For example: ["topic1", "topic2", "topic3"]

Text chunk:
{preview_content}
...

Return the topics in a structured JSON format:
```json
{{
  "topics": ["Primary topic 1", "Secondary topic 2", "Keyword topic 3"]
}}
```
"""

    def _parse_topics_from_llm_output(self, llm_output: str) -> List[str]:
        """
        Parse topics from LLM output
        
        Args:
            llm_output: Text output from LLM
            
        Returns:
            List of topic strings
        """
        try:
            # Try to extract JSON from output
            json_match = re.search(r'```json\s*(.*?)\s*```', llm_output, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                data = json.loads(json_str)
                topics = data.get("topics", [])
                if isinstance(topics, list) and all(isinstance(topic, str) for topic in topics):
                    return topics
                else:
                    logger.warning(f"Parsed 'topics' is not a list of strings: {topics}")
                    return []
            
            # Fallback parsing for non-JSON responses
            logger.warning(f"Could not parse JSON topics from LLM output, trying text extraction")
            
            # Try to extract a list from text
            if "topics:" in llm_output.lower():
                lines = llm_output.splitlines()
                for line in lines:
                    if line.lower().strip().startswith("topics:"):
                        try:
                            # Assuming topics are comma-separated after "topics:"
                            extracted = [t.strip().replace('"',"") for t in line.split(":", 1)[1].strip().split(",") if t.strip()]
                            if extracted: 
                                return extracted
                        except Exception as e:
                            logger.warning(f"Failed to extract topics from line: {line}, error: {e}")
            
            # Try to extract a list with regex
            list_match = re.search(r'\[(.*?)\]', llm_output, re.DOTALL)
            if list_match:
                list_content = list_match.group(1)
                # Parse comma-separated items, handling both quoted and unquoted strings
                topics = re.findall(r'"([^"]*?)"|\'([^\']*?)\'|(\w+)', list_content)
                return [next(s for s in t if s) for t in topics]
            
            return []
            
        except Exception as e:
            logger.error(f"Error parsing topics from LLM output: {e}")
            return []
