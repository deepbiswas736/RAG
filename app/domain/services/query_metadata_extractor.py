import re
import logging
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass, field
import json
import asyncio

logger = logging.getLogger(__name__)

@dataclass
class QueryMetadata:
    """Class to represent structured metadata extracted from a query"""
    # Entity types found in the query
    entities: Dict[str, List[str]] = field(default_factory=lambda: {
        "person": [],
        "organization": [],
        "location": [],
        "time": [],
        "other": []
    })
    
    # Topic categorization
    topics: List[str] = field(default_factory=list)
    
    # Query classification
    query_type: str = "informational"  # informational, comparative, exploratory
    
    # Time references
    time_period: Optional[str] = None
    
    # Additional context
    context_hints: Dict[str, str] = field(default_factory=dict)
    
    # Query intent
    intent: Optional[str] = None
    
    # The processed version of the query (with potential rewrites)
    processed_query: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary representation"""
        return {
            "entities": self.entities,
            "topics": self.topics,
            "query_type": self.query_type,
            "time_period": self.time_period,
            "context_hints": self.context_hints,
            "intent": self.intent,
            "processed_query": self.processed_query
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'QueryMetadata':
        """Create from dictionary representation"""
        metadata = cls()
        metadata.entities = data.get("entities", {})
        metadata.topics = data.get("topics", [])
        metadata.query_type = data.get("query_type", "informational")
        metadata.time_period = data.get("time_period")
        metadata.context_hints = data.get("context_hints", {})
        metadata.intent = data.get("intent")
        metadata.processed_query = data.get("processed_query")
        return metadata
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_json(cls, json_str: str) -> 'QueryMetadata':
        """Create from JSON string"""
        data = json.loads(json_str)
        return cls.from_dict(data)


class QueryMetadataExtractor:
    """
    Extracts structured metadata from natural language queries to enhance
    the RAG retrieval process. This helps better understand the user's intent
    and provides additional context for the search.
    """
    
    def __init__(self, llm_manager=None):
        """
        Initialize the metadata extractor.
        
        Args:
            llm_manager: Optional LLM manager for advanced extraction
        """
        self.llm_manager = llm_manager
        # Initialize pattern libraries
        self._init_patterns()
        
    def _init_patterns(self):
        """Initialize regex patterns for basic extraction"""
        # Person name patterns (already used in query service)
        self.person_patterns = [
            r"([A-Za-z\s]+)'s\s+(\w+)",  # "John Smith's skills"
            r"(\w+)\s+of\s+([A-Za-z\s]+)",  # "skills of John Smith"
            r"(\w+)\s+for\s+([A-Za-z\s]+)",  # "skills for John Smith"
            r"what\s+(\w+)\s+does\s+([A-Za-z\s]+)\s+have",  # "what skills does John Smith have"
            r"what\s+are\s+([A-Za-z\s]+)'s\s+(\w+)"  # "what are John Smith's skills"
        ]
        
        # Time reference patterns
        self.time_patterns = [
            r"in\s+(\d{4})",  # "in 2023" 
            r"from\s+(\d{4})\s+to\s+(\d{4})",  # "from 2020 to 2023"
            r"before\s+(\d{4})",  # "before 2020"
            r"after\s+(\d{4})",  # "after 2020"
            r"recent|latest|current|newest|today|now",  # Recency indicators
            r"past\s+(\d+)\s+(day|week|month|year)s?",  # "past 3 months"
            r"last\s+(\d+)\s+(day|week|month|year)s?"  # "last 2 years"
        ]
        
        # Organization patterns
        self.org_patterns = [
            r"at\s+([A-Z][A-Za-z0-9\s&]+)",  # "at Google"
            r"in\s+([A-Z][A-Za-z0-9\s&]+)",  # "in Microsoft"
            r"for\s+([A-Z][A-Za-z0-9\s&]+)",  # "for Amazon"
            r"with\s+([A-Z][A-Za-z0-9\s&]+)"  # "with IBM"
        ]
        
        # Location patterns
        self.location_patterns = [
            r"in\s+([A-Z][A-Za-z\s]+(?:City|State|County|Country|Province))",  # "in New York City"
            r"from\s+([A-Z][A-Za-z\s]+)",  # "from California"
            r"at\s+([A-Z][A-Za-z\s]+)"  # "at Chicago"
        ]
        
        # Topic patterns for common domains
        self.topic_patterns = {
            "technology": [
                r"software|hardware|programming|code|developer|IT|tech|computer|AI|ML|artificial intelligence|machine learning|data science"
            ],
            "business": [
                r"business|finance|marketing|sales|management|strategy|leadership|entrepreneurship|startup"
            ],
            "education": [
                r"education|school|university|college|degree|teaching|learning|student|academic|course"
            ],
            "healthcare": [
                r"health|medical|healthcare|doctor|hospital|patient|treatment|medicine|nursing|pharma"
            ]
        }
        
        # Query type patterns
        self.query_types = {
            "comparative": [
                r"compare|versus|vs\.|difference|better|worse|advantages|disadvantages|pros|cons"
            ],
            "exploratory": [
                r"how|explain|describe|elaborate|tell me about|what is|who is|where is|when"
            ],
            "factual": [
                r"what|who|when|where|which|why|did|is|are|was|were"
            ]
        }
        
    def extract_metadata(self, query: str) -> QueryMetadata:
        """
        Extract structured metadata from a query string synchronously.
        This method performs fast rule-based extraction without waiting for LLM.
        
        Args:
            query: The user's query text
            
        Returns:
            QueryMetadata object containing extracted metadata
        """
        metadata = QueryMetadata()
        metadata.processed_query = query  # Start with original query
        
        # Simple rule-based extraction - synchronous for fast results
        self._extract_basic_metadata(query, metadata)
        
        return metadata
    
    def extract_metadata_with_llm_sync(self, query: str) -> QueryMetadata:
        """
        Extract metadata with LLM synchronously for queries.
        This blocks until LLM completes the extraction, but ensures high precision
        for query understanding.
        
        Args:
            query: The user's query text
            
        Returns:
            QueryMetadata object containing LLM-enhanced metadata
        """
        if not self.llm_manager:
            return self.extract_metadata(query)
            
        # Start with basic extraction
        metadata = self.extract_metadata(query)
        
        try:
            # Run LLM enhancement synchronously
            # We use the event loop but wait for completion
            loop = asyncio.get_event_loop()
            enhanced_metadata = loop.run_until_complete(
                self._enhance_metadata_with_llm(query, metadata)
            )
            return enhanced_metadata
        except Exception as e:
            logger.error(f"Error in synchronous LLM metadata extraction: {e}")
            # Fall back to basic metadata
            return metadata
    
    async def _enhance_metadata_with_llm(self, query: str, metadata: QueryMetadata) -> QueryMetadata:
        """
        Internal method to enhance metadata with LLM and return the enhanced version.
        
        Args:
            query: Original query string
            metadata: QueryMetadata object with basic extractions to enhance
            
        Returns:
            Enhanced QueryMetadata object
        """
        # Create a copy to avoid modifying the original during async operations
        enhanced_metadata = QueryMetadata.from_dict(metadata.to_dict())
        
        if not self.llm_manager:
            return enhanced_metadata
            
        try:
            # Create a prompt for the LLM to extract metadata
            basic_metadata = json.dumps(metadata.to_dict(), indent=2)
            
            prompt = f"""Analyze this query and extract structured metadata to help with information retrieval.
            
Query: "{query}"

I already extracted some basic metadata:
{basic_metadata}

Please enhance this metadata by:
1. Identifying any additional entities (people, organizations, locations, time references)
2. Determining the main topics and subtopics
3. Understanding the intent behind the query
4. Suggesting a query rewrite that might improve search results

Return your analysis as valid JSON with these fields:
- entities: Dictionary with person, organization, location, time, other (arrays of strings)
- topics: Array of topic strings
- query_type: String (informational, comparative, exploratory) 
- time_period: String (if applicable)
- intent: String describing the intent
- processed_query: String with an improved version of the query

Only return the JSON object, no other text.
"""
            
            # Get response from LLM
            llm_response = await self.llm_manager.generate_response(prompt, [])
            
            # Parse JSON response
            try:
                # Try to extract JSON from the response (handle potential text before/after)
                # Look for a JSON block in the response
                json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    enhanced_data = json.loads(json_str)
                    
                    # Update metadata with enhanced data
                    if "entities" in enhanced_data:
                        for entity_type, entities in enhanced_data["entities"].items():
                            if entity_type in enhanced_metadata.entities:
                                # Add new entities while avoiding duplicates
                                existing = set(enhanced_metadata.entities[entity_type])
                                for entity in entities:
                                    if entity not in existing:
                                        enhanced_metadata.entities[entity_type].append(entity)
                    
                    if "topics" in enhanced_data:
                        existing_topics = set(enhanced_metadata.topics)
                        for topic in enhanced_data["topics"]:
                            if topic not in existing_topics:
                                enhanced_metadata.topics.append(topic)
                    
                    if "query_type" in enhanced_data:
                        enhanced_metadata.query_type = enhanced_data["query_type"]
                    
                    if "time_period" in enhanced_data and enhanced_data["time_period"]:
                        enhanced_metadata.time_period = enhanced_data["time_period"]
                    
                    if "intent" in enhanced_data and enhanced_data["intent"]:
                        enhanced_metadata.intent = enhanced_data["intent"]
                    
                    if "processed_query" in enhanced_data and enhanced_data["processed_query"]:
                        enhanced_metadata.processed_query = enhanced_data["processed_query"]
                    
                    logger.info(f"Enhanced query metadata with LLM for: '{query}'")
                else:
                    logger.warning(f"Failed to extract JSON from LLM response: {llm_response[:100]}...")
            
            except Exception as e:
                logger.error(f"Error parsing LLM response for metadata extraction: {e}")
                logger.debug(f"Problematic LLM response: {llm_response[:200]}...")
        
        except Exception as e:
            logger.error(f"Error enhancing metadata with LLM: {e}")
            
        return enhanced_metadata
        
    def extract_metadata_with_llm_async(self, query: str) -> QueryMetadata:
        """
        Extract and enhance metadata asynchronously using LLM.
        
        Args:
            query: The user's query text
            
        Returns:
            QueryMetadata object containing extracted metadata
        """
        # Get basic metadata immediately
        metadata = self.extract_metadata(query)
        
        # Queue LLM enhancement asynchronously if needed
        if self.llm_manager:
            # Return immediately, let the enhancement happen in background
            asyncio.create_task(self._enhance_with_llm_and_store(query, metadata))
            
        return metadata
    
    def _extract_basic_metadata(self, query: str, metadata: QueryMetadata):
        """
        Extract metadata using rule-based patterns synchronously.
        
        Args:
            query: The query string
            metadata: QueryMetadata object to update
        """
        query_lower = query.lower()
        
        # Extract person entities
        for pattern in self.person_patterns:
            matches = re.finditer(pattern, query, re.IGNORECASE)
            for match in matches:
                # The person name is typically in the second group
                if len(match.groups()) >= 2:
                    attribute = match.group(1).strip().lower()
                    person_name = match.group(2).strip()
                    metadata.entities["person"].append(person_name)
                    # Add context hint about what we're looking for
                    metadata.context_hints[attribute] = person_name
                    # Check if it's a skills query
                    if "skill" in attribute:
                        metadata.topics.append("skills")
                        metadata.intent = "find_skills"
                elif len(match.groups()) >= 1:
                    # If only one group, assume it's the person
                    person_name = match.group(1).strip()
                    metadata.entities["person"].append(person_name)
        
        # Extract time references
        for pattern in self.time_patterns:
            matches = re.finditer(pattern, query_lower)
            for match in matches:
                time_ref = match.group(0)
                metadata.entities["time"].append(time_ref)
                
                # Set time period if not already set
                if not metadata.time_period:
                    metadata.time_period = time_ref
        
        # Extract organizations
        for pattern in self.org_patterns:
            matches = re.finditer(pattern, query)
            for match in matches:
                if len(match.groups()) >= 1:
                    org_name = match.group(1).strip()
                    metadata.entities["organization"].append(org_name)
        
        # Extract locations
        for pattern in self.location_patterns:
            matches = re.finditer(pattern, query)
            for match in matches:
                if len(match.groups()) >= 1:
                    location = match.group(1).strip()
                    metadata.entities["location"].append(location)
        
        # Identify topics
        for topic, patterns in self.topic_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    metadata.topics.append(topic)
                    break  # Only add each topic once
        
        # Determine query type
        for q_type, patterns in self.query_types.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    metadata.query_type = q_type
                    break
            
            # If we found a match, no need to check other types
            if metadata.query_type != "informational":
                break
    
    async def _enhance_with_llm_and_store(self, query: str, metadata: QueryMetadata):
        """
        Background task to enhance metadata with LLM and store results.
        This method allows the main query processing to continue without waiting.
        
        Args:
            query: Original query string
            metadata: QueryMetadata object with basic extractions to enhance
        """
        try:
            await self._enhance_with_llm(query, metadata)
            # Here you could store the enhanced metadata in a cache or database
            # for future use, or trigger any follow-up actions
            logger.info(f"Completed background LLM metadata enhancement for: '{query}'")
        except Exception as e:
            logger.error(f"Error in background LLM metadata enhancement: {e}")
    
    async def _enhance_with_llm(self, query: str, metadata: QueryMetadata):
        """
        Use LLM to enhance metadata extraction with more advanced understanding.
        
        Args:
            query: Original query string
            metadata: QueryMetadata object with basic extractions to enhance
        """
        if not self.llm_manager:
            return
        
        try:
            # Create a prompt for the LLM to extract metadata
            basic_metadata = json.dumps(metadata.to_dict(), indent=2)
            
            prompt = f"""Analyze this query and extract structured metadata to help with information retrieval.
            
Query: "{query}"

I already extracted some basic metadata:
{basic_metadata}

Please enhance this metadata by:
1. Identifying any additional entities (people, organizations, locations, time references)
2. Determining the main topics and subtopics
3. Understanding the intent behind the query
4. Suggesting a query rewrite that might improve search results

Return your analysis as valid JSON with these fields:
- entities: Dictionary with person, organization, location, time, other (arrays of strings)
- topics: Array of topic strings
- query_type: String (informational, comparative, exploratory) 
- time_period: String (if applicable)
- intent: String describing the intent
- processed_query: String with an improved version of the query

Only return the JSON object, no other text.
"""
            
            # Get response from LLM
            llm_response = await self.llm_manager.generate_response(prompt, [])
            
            # Parse JSON response
            try:
                # Try to extract JSON from the response (handle potential text before/after)
                import json
                import re
                
                # Look for a JSON block in the response
                json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    enhanced_data = json.loads(json_str)
                    
                    # Update metadata with enhanced data
                    if "entities" in enhanced_data:
                        for entity_type, entities in enhanced_data["entities"].items():
                            if entity_type in metadata.entities:
                                # Add new entities while avoiding duplicates
                                existing = set(metadata.entities[entity_type])
                                for entity in entities:
                                    if entity not in existing:
                                        metadata.entities[entity_type].append(entity)
                    
                    if "topics" in enhanced_data:
                        existing_topics = set(metadata.topics)
                        for topic in enhanced_data["topics"]:
                            if topic not in existing_topics:
                                metadata.topics.append(topic)
                    
                    if "query_type" in enhanced_data:
                        metadata.query_type = enhanced_data["query_type"]
                    
                    if "time_period" in enhanced_data and enhanced_data["time_period"]:
                        metadata.time_period = enhanced_data["time_period"]
                    
                    if "intent" in enhanced_data and enhanced_data["intent"]:
                        metadata.intent = enhanced_data["intent"]
                    
                    if "processed_query" in enhanced_data and enhanced_data["processed_query"]:
                        metadata.processed_query = enhanced_data["processed_query"]
                    
                    logger.info(f"Enhanced query metadata with LLM for: '{query}'")
                else:
                    logger.warning(f"Failed to extract JSON from LLM response: {llm_response[:100]}...")
            
            except Exception as e:
                logger.error(f"Error parsing LLM response for metadata extraction: {e}")
                logger.debug(f"Problematic LLM response: {llm_response[:200]}...")
                
        except Exception as e:
            logger.error(f"Error using LLM for metadata enhancement: {e}")