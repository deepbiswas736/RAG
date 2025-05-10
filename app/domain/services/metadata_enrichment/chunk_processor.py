"""
Chunk processor for metadata extraction.
"""
import logging
import re
from typing import Dict, Optional, List, Any

logger = logging.getLogger(__name__)

class ChunkProcessor:
    """
    Processes document chunks to extract metadata with high confidence.
    """
    
    def __init__(self, llm_manager):
        """
        Initialize the chunk processor.
        
        Args:
            llm_manager: LLM manager for enriching metadata with AI
        """
        self.llm_manager = llm_manager
        
    async def process_chunk(self, chunk_content: str, chunk_id: str, position: int, doc_title: str) -> Optional[Dict]:
        """
        Process a single chunk for metadata extraction with strict validation.
        
        Args:
            chunk_content: The text content of the chunk
            chunk_id: The ID of the chunk
            position: The position of the chunk in the document
            doc_title: The title of the parent document
            
        Returns:
            Dictionary with extracted metadata or None if processing fails
        """
        try:
            # Extract metadata with LLM
            prompt = self._create_chunk_analysis_prompt(chunk_content, doc_title)
            llm_response = await self.llm_manager.generate_response(prompt, [])
            
            # Parse the response
            from ..metadata_extraction_service import MetadataExtractionService
            extraction_service = MetadataExtractionService(self.llm_manager)
            metadata = extraction_service._parse_llm_metadata_response(llm_response)
            
            if not metadata:
                logger.warning(f"No metadata extracted for chunk {chunk_id} at position {position}")
                return None
            
            # Validate person information
            if 'person_name' in metadata:
                confidence = self._validate_person_info(metadata['person_name'], chunk_content)
                if confidence < 0.85:
                    logger.info(f"Removed low confidence person name '{metadata['person_name']}' from chunk {chunk_id}")
                    del metadata['person_name']
            
            # Add chunk position and metadata
            result = {
                'chunk_id': chunk_id,
                'position': position,
                'confidence_scores': self._calculate_confidence_scores(metadata),
                'metadata': metadata
            }
            
            return result
        
        except Exception as e:
            logger.error(f"Error processing chunk {chunk_id} at position {position}: {e}")
            return None
    
    def _create_chunk_analysis_prompt(self, content: str, doc_title: str) -> str:
        """
        Create a prompt for extracting metadata from a chunk.
        
        Args:
            content: The chunk content
            doc_title: The document title
            
        Returns:
            Prompt for LLM
        """
        return f"""Extract metadata from this document chunk titled "{doc_title}".
Return your analysis as JSON with the following fields (only include if you have high confidence):
- person_name: The full name of the person if this is a personal document (like a resume)
- topics: List of main topics/themes discussed in this chunk
- keywords: List of important keywords from this chunk
- entities: Dictionary of entity types and their values (like organizations, locations, dates)
- summary: A brief summary of this chunk's content

Document chunk:
{content}

Respond with only the JSON object, properly formatted. Only include the person_name if you are HIGHLY CONFIDENT (>85%).
Example format:
{{
  "person_name": "John Smith",
  "topics": ["Machine Learning", "Data Science"],
  "keywords": ["Python", "TensorFlow", "Neural Networks"],
  "entities": {{
    "PERSON": ["John Smith"],
    "ORG": ["Google", "Microsoft"],
    "LOC": ["San Francisco", "New York"],
    "DATE": ["2020-2022", "January 2019"]
  }},
  "summary": "This chunk describes John Smith's experience in machine learning projects at Google."
}}
"""
    
    def _validate_person_info(self, name: str, content: str) -> float:
        """
        Validate extracted person name with confidence score.
        
        Args:
            name: The extracted person name
            content: The content to validate against
            
        Returns:
            Confidence score between 0 and 1
        """
        if not name:
            return 0.0
        
        confidence = 0.5  # Base confidence
        
        # Check name format (First Last)
        if re.match(r'^[A-Z][a-z]+ [A-Z][a-z]+$', name):
            confidence += 0.2
            
        # Check if name appears in the first 20% of content
        first_fifth = content[:int(len(content)/5)]
        if name in first_fifth:
            confidence += 0.2
            
        # Check for common resume headers near the name
        context_window = 200  # characters
        name_index = content.find(name)
        
        if name_index != -1:
            context = content[max(0, name_index-context_window):min(len(content), name_index+context_window)]
            resume_indicators = ['resume', 'cv', 'curriculum vitae', 'profile', 'professional', 'experience']
            
            for indicator in resume_indicators:
                if indicator.lower() in context.lower():
                    confidence += 0.1
                    break
        
        # Cap confidence at 1.0
        return min(confidence, 1.0)
    
    def _calculate_confidence_scores(self, metadata: Dict) -> Dict[str, float]:
        """
        Calculate confidence scores for metadata fields.
        
        Args:
            metadata: The extracted metadata
            
        Returns:
            Dictionary with confidence scores
        """
        scores = {}
        
        # Person name confidence (already calculated in validate_person_info)
        if 'person_name' in metadata:
            scores['person_name'] = 0.85  # Minimum threshold to be included
        
        # Keywords confidence
        if 'keywords' in metadata and isinstance(metadata['keywords'], list):
            # More keywords = lower confidence per keyword
            num_keywords = len(metadata['keywords'])
            scores['keywords'] = max(0.5, 1.0 - (num_keywords * 0.02))  # 50+ keywords would be suspicious
        
        # Entities confidence
        if 'entities' in metadata and isinstance(metadata['entities'], dict):
            entity_counts = sum(len(entities) for entities in metadata['entities'].values() if isinstance(entities, list))
            scores['entities'] = max(0.5, 1.0 - (entity_counts * 0.01))
        
        # Topics confidence - typically high
        if 'topics' in metadata:
            scores['topics'] = 0.8
        
        return scores
