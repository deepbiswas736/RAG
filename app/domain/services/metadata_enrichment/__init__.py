"""
Metadata Enrichment Service package.
This package contains components for processing document chunks and extracting metadata.
"""

from .chunk_processor import ChunkProcessor
from .metadata_aggregator import MetadataAggregator
from .embedding_processor import EmbeddingProcessor

__all__ = ['ChunkProcessor', 'MetadataAggregator', 'EmbeddingProcessor']
