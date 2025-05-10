"""
Metadata aggregator for combining chunk-level metadata.
"""
import logging
from typing import Dict, List, Optional
from collections import Counter

logger = logging.getLogger(__name__)

class MetadataAggregator:
    """
    Aggregates metadata from multiple document chunks and generates global context.
    """
    
    def __init__(self, llm_manager):
        """
        Initialize the metadata aggregator.
        
        Args:
            llm_manager: LLM manager for enriching metadata with AI
        """
        self.llm_manager = llm_manager
    
    async def aggregate_metadata(self, chunk_metadata: List[Dict], doc_title: str) -> Dict:
        """
        Aggregate metadata from multiple chunks into a cohesive document metadata.
        
        Args:
            chunk_metadata: List of metadata dictionaries from chunks
            doc_title: Document title for context
            
        Returns:
            Aggregated metadata dictionary
        """
        if not chunk_metadata:
            logger.warning(f"No chunk metadata to aggregate for document: {doc_title}")
            return {}
        
        # Extract all chunk content metadata
        metadata_entries = [item.get('metadata', {}) for item in chunk_metadata if 'metadata' in item]
        
        # Create base aggregated metadata
        aggregated = {
            'person_name': None,
            'topics': [],
            'keywords': [],
            'entities': {
                'PERSON': [],
                'ORG': [],
                'LOC': [],
                'DATE': []
            },
            'summary': ""
        }
        
        # Collect all content for global extraction
        all_content = self._extract_content_for_global_analysis(chunk_metadata)
        
        # First pass: Aggregate using frequency analysis
        aggregated = self._frequency_based_aggregation(metadata_entries)
        
        # Second pass: Use LLM to verify entities and generate global context
        try:
            global_metadata = await self._verify_with_llm(all_content, aggregated, doc_title)
            aggregated.update(global_metadata)
        except Exception as e:
            logger.error(f"Error during LLM verification: {e}")
        
        # Add metaEmbeddings placeholder (will be filled by embedding processor)
        aggregated['metaEmbeddings'] = {}
        
        return aggregated
    
    def _extract_content_for_global_analysis(self, chunk_metadata: List[Dict]) -> str:
        """
        Extract representative content for global analysis.
        
        Args:
            chunk_metadata: List of metadata dictionaries from chunks
            
        Returns:
            String with representative content for global analysis
        """
        # This would extract key snippets from each chunk to build a context
        # But since we don't have the actual content here, we'll use metadata
        # In a real implementation, you would include snippets from each chunk
        
        snippets = []
        
        for item in chunk_metadata:
            metadata = item.get('metadata', {})
            position = item.get('position', 0)
            
            # Add summary if available
            if 'summary' in metadata:
                snippets.append(f"Chunk {position}: {metadata['summary']}")
                
            # Add entities
            if 'entities' in metadata:
                entities = []
                for ent_type, ent_list in metadata.get('entities', {}).items():
                    if isinstance(ent_list, list):
                        entities.extend([f"{ent} ({ent_type})" for ent in ent_list[:3]])
                
                if entities:
                    snippets.append(f"Entities in chunk {position}: {', '.join(entities)}")
        
        return "\n\n".join(snippets)
    
    def _frequency_based_aggregation(self, metadata_entries: List[Dict]) -> Dict:
        """
        Aggregate metadata using frequency analysis.
        
        Args:
            metadata_entries: List of metadata dictionaries
            
        Returns:
            Aggregated metadata based on frequencies
        """
        # Track frequencies for deduplication
        person_counter = Counter()
        topic_counter = Counter()
        keyword_counter = Counter()
        entity_counters = {
            'PERSON': Counter(),
            'ORG': Counter(), 
            'LOC': Counter(),
            'DATE': Counter()
        }
        summaries = []
        
        # Process each metadata entry
        for metadata in metadata_entries:
            # Person name
            if metadata.get("person_name"):
                name = metadata["person_name"].strip()
                if name:
                    person_counter[name] += 1
            
            # Topics
            if "topics" in metadata and isinstance(metadata["topics"], list):
                for topic in metadata["topics"]:
                    topic = topic.strip().lower()
                    if topic:
                        topic_counter[topic] += 1
            
            # Keywords
            if "keywords" in metadata and isinstance(metadata["keywords"], list):
                for keyword in metadata["keywords"]:
                    keyword = keyword.strip().lower()
                    if keyword:
                        keyword_counter[keyword] += 1
            
            # Entities
            if "entities" in metadata and isinstance(metadata["entities"], dict):
                for entity_type, entities in metadata["entities"].items():
                    if entity_type in entity_counters and isinstance(entities, list):
                        for entity in entities:
                            entity = entity.strip()
                            if entity:
                                entity_counters[entity_type][entity] += 1
            
            # Save summaries
            if "summary" in metadata and metadata["summary"]:
                summaries.append(metadata["summary"])
        
        # Build aggregated metadata
        aggregated = {
            "person_name": person_counter.most_common(1)[0][0] if person_counter else None,
            "topics": [k for k, _ in topic_counter.most_common(10)],
            "keywords": [k for k, _ in keyword_counter.most_common(15)],
            "entities": {}
        }
        
        # Add entities with at least 2 occurrences
        for entity_type, counter in entity_counters.items():
            aggregated["entities"][entity_type] = [
                entity for entity, count in counter.most_common(5) if count >= 2
            ]
        
        # Create a consolidated summary if we have summaries
        if summaries:
            aggregated["summary"] = summaries[0]  # Simple approach: use first summary
        
        return aggregated
    
    async def _verify_with_llm(self, content_context: str, initial_metadata: Dict, doc_title: str) -> Dict:
        """
        Use LLM to verify and enhance the aggregated metadata.
        
        Args:
            content_context: Extracted content for global analysis
            initial_metadata: Initially aggregated metadata
            doc_title: Document title
            
        Returns:
            Enhanced metadata dictionary
        """
        # Create the prompt for LLM
        prompt = self._create_verification_prompt(content_context, initial_metadata, doc_title)
        
        # Get LLM response
        llm_response = await self.llm_manager.generate_response(prompt, [])
        
        # Parse the response
        from ..metadata_extraction_service import MetadataExtractionService
        extraction_service = MetadataExtractionService(self.llm_manager)
        verified_metadata = extraction_service._parse_llm_metadata_response(llm_response)
        
        # Only override specific fields if they exist in the verified metadata
        result = {}
        
        if verified_metadata.get('person_name') and len(verified_metadata['person_name']) > 2:
            result['person_name'] = verified_metadata['person_name']
            
        if 'summary' in verified_metadata and len(verified_metadata['summary']) > 20:
            result['summary'] = verified_metadata['summary']
            
        # Add global context if available
        if 'global_context' in verified_metadata:
            result['global_context'] = verified_metadata['global_context']
            
        return result
    
    def _create_verification_prompt(self, content_context: str, initial_metadata: Dict, doc_title: str) -> str:
        """
        Create a prompt for verifying and enhancing metadata.
        
        Args:
            content_context: Extracted content for global analysis
            initial_metadata: Initially aggregated metadata
            doc_title: Document title
            
        Returns:
            Prompt string
        """
        # Format the initial metadata for the prompt
        person_name = initial_metadata.get('person_name', 'Unknown')
        topics = ", ".join(initial_metadata.get('topics', []))
        keywords = ", ".join(initial_metadata.get('keywords', []))
        
        entities = []
        for entity_type, entity_list in initial_metadata.get('entities', {}).items():
            if entity_list:
                entities.append(f"{entity_type}: {', '.join(entity_list)}")
        entities_text = "\n".join(entities)
        
        return f"""Verify and enhance metadata for document titled "{doc_title}".
        
Initial metadata extracted:
- Person name: {person_name}
- Topics: {topics}
- Keywords: {keywords}
- Entities:
{entities_text}

Content snippets from document:
{content_context}

Based on the content snippets, verify the following information and return as JSON:
1. The person_name (only include if highly confident, otherwise leave blank)
2. A global_context that explains what this document is about overall
3. A comprehensive summary of the content

Respond with only the JSON object, properly formatted. Example format:
{{
  "person_name": "John Smith",
  "global_context": "This is a resume document for a data scientist with 5 years of experience",
  "summary": "John Smith is a data scientist with expertise in machine learning, focusing on natural language processing. He has worked for Google and Microsoft on various projects involving TensorFlow and neural network implementations."
}}
"""
