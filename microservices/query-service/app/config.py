"""
Configuration module for the Query Service
-----------------------------------------
Configuration settings loaded from environment variables
"""

import os
from typing import Any, Dict, Optional


# API configuration
ROOT_PATH = os.getenv("ROOT_PATH", "")
API_PREFIX = os.getenv("API_PREFIX", "/api/v1")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Service URLs
LLM_SERVICE_URL = os.getenv("LLM_SERVICE_URL", "http://llm-service:8001")
DOCUMENT_SERVICE_URL = os.getenv("DOCUMENT_SERVICE_URL", "http://document-service:8000")

# Timeouts
LLM_SERVICE_TIMEOUT = float(os.getenv("LLM_SERVICE_TIMEOUT", "30.0"))
DOCUMENT_SERVICE_TIMEOUT = float(os.getenv("DOCUMENT_SERVICE_TIMEOUT", "30.0"))

# MongoDB Configuration
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://user:password@mongodb:27017")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "rag_db")
MONGODB_COLLECTION = os.getenv("MONGODB_COLLECTION", "queries")
MONGODB_RESPONSE_COLLECTION = os.getenv("MONGODB_RESPONSE_COLLECTION", "responses")
MONGODB_CONVERSATIONS_COLLECTION = os.getenv("MONGODB_CONVERSATIONS_COLLECTION", "conversations")

# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_TOPIC_QUERIES = os.getenv("KAFKA_TOPIC_QUERIES", "rag_queries")

# Search and ranking configuration
DEFAULT_SEARCH_LIMIT = int(os.getenv("DEFAULT_SEARCH_LIMIT", "10"))
DEFAULT_SIMILARITY_THRESHOLD = float(os.getenv("DEFAULT_SIMILARITY_THRESHOLD", "0.65"))
DEFAULT_RANKING_METHOD = os.getenv("DEFAULT_RANKING_METHOD", "hybrid")
ENABLE_METADATA_SEARCH = os.getenv("ENABLE_METADATA_SEARCH", "True").lower() == "true"

# Vector search configuration
VECTOR_SEARCH_CANDIDATE_MULTIPLIER = int(os.getenv("VECTOR_SEARCH_CANDIDATE_MULTIPLIER", "3"))
MAX_CANDIDATES = int(os.getenv("MAX_CANDIDATES", "30"))

# Vector ranking weights - configurable per ranking method
VECTOR_WEIGHTS = {
    "hybrid": {
        "vector_similarity": float(os.getenv("HYBRID_VECTOR_WEIGHT", "0.6")),
        "keyword_match": float(os.getenv("HYBRID_KEYWORD_WEIGHT", "0.15")),
        "position_score": float(os.getenv("HYBRID_POSITION_WEIGHT", "0.10")),
        "metadata_score": float(os.getenv("HYBRID_METADATA_WEIGHT", "0.15"))
    },
    "keyword_boost": {
        "vector_similarity": float(os.getenv("KEYWORD_BOOST_VECTOR_WEIGHT", "0.4")),
        "keyword_match": float(os.getenv("KEYWORD_BOOST_KEYWORD_WEIGHT", "0.3")),
        "position_score": float(os.getenv("KEYWORD_BOOST_POSITION_WEIGHT", "0.1")),
        "metadata_score": float(os.getenv("KEYWORD_BOOST_METADATA_WEIGHT", "0.2"))
    },
    "metadata_focus": {
        "vector_similarity": float(os.getenv("METADATA_FOCUS_VECTOR_WEIGHT", "0.4")),
        "keyword_match": float(os.getenv("METADATA_FOCUS_KEYWORD_WEIGHT", "0.15")),
        "position_score": float(os.getenv("METADATA_FOCUS_POSITION_WEIGHT", "0.05")),
        "metadata_score": float(os.getenv("METADATA_FOCUS_METADATA_WEIGHT", "0.4"))
    }
}

# Metadata field configuration
DEFAULT_METADATA_FIELDS = os.getenv("DEFAULT_METADATA_FIELDS", "title,author,keywords,topic,summary").split(",")
METADATA_IMPORTANCE = {
    "title": float(os.getenv("METADATA_WEIGHT_TITLE", "0.3")),
    "author": float(os.getenv("METADATA_WEIGHT_AUTHOR", "0.1")),
    "keywords": float(os.getenv("METADATA_WEIGHT_KEYWORDS", "0.2")),
    "topic": float(os.getenv("METADATA_WEIGHT_TOPIC", "0.2")),
    "summary": float(os.getenv("METADATA_WEIGHT_SUMMARY", "0.2"))
}

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Service Information
SERVICE_NAME = "Query Service"
SERVICE_VERSION = "1.0.0"
SERVICE_DESCRIPTION = "RAG microservice for efficient query processing"

def get_settings() -> Dict[str, Any]:
    """
    Get all settings as a dictionary
    
    Returns:
        Dictionary of configuration settings
    """
    return {k: v for k, v in globals().items() 
            if k.isupper() and not k.startswith('_')}
