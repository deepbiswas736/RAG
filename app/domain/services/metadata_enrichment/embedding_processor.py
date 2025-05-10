"""
Embedding processor for generating and storing embeddings.
"""
import logging
import json
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

class EmbeddingProcessor:
    """
    Generates and stores embeddings for document chunks and metadata.
    """
    
    def __init__(self, embedding_model):
        """
        Initialize the embedding processor.
        
        Args:
            embedding_model: Model for generating embeddings
        """
        self.embedding_model = embedding_model
    
    async def process_embeddings(self, chunks: List[Dict], metadata: Dict) -> Dict:
        """
        Create embeddings for chunks and metadata.
        
        Args:
            chunks: List of document chunks
            metadata: Aggregated document metadata
            
        Returns:
            Dictionary with metaEmbeddings
        """
        try:
            # Generate chunk embeddings
            chunk_embeddings = await self._generate_chunk_embeddings(chunks)
            
            # Generate metadata embedding
            metadata_embedding = await self._generate_metadata_embedding(metadata)
            
            # Combine into metaEmbeddings structure
            meta_embeddings = {
                'chunk_embeddings': chunk_embeddings,
                'metadata_embedding': metadata_embedding,
                'document_id': metadata.get('document_id', ''),
            }
            
            logger.info(f"Generated embeddings for {len(chunks)} chunks")
            return {'metaEmbeddings': meta_embeddings}
            
        except Exception as e:
            logger.error(f"Error processing embeddings: {e}")
            return {'metaEmbeddings': {}}
    
    async def _generate_chunk_embeddings(self, chunks: List[Dict]) -> List[Dict]:
        """
        Generate embeddings for document chunks.
        
        Args:
            chunks: List of document chunks
            
        Returns:
            List of chunk embeddings
        """
        chunk_embeddings = []
        
        for chunk in chunks:
            try:
                # Generate embedding for chunk content
                content = chunk.get('content', '')
                
                if not content:
                    logger.warning(f"No content found for chunk {chunk.get('id', 'unknown')}")
                    continue
                
                embedding = await self.embedding_model.create_embedding(content)
                
                # Create the chunk embedding entry
                chunk_embedding = {
                    'chunk_id': chunk.get('id', ''),
                    'position': chunk.get('position', 0),
                    'embedding': embedding,
                    'metadata_mapping': {
                        'topics': chunk.get('metadata', {}).get('topics', []),
                        'keywords': chunk.get('metadata', {}).get('keywords', []),
                        'entities': chunk.get('metadata', {}).get('entities', {})
                    }
                }
                
                chunk_embeddings.append(chunk_embedding)
                
            except Exception as e:
                logger.error(f"Error generating embedding for chunk {chunk.get('id', 'unknown')}: {e}")
        
        return chunk_embeddings
    
    async def _generate_metadata_embedding(self, metadata: Dict) -> Dict:
        """
        Generate embedding for document metadata.
        
        Args:
            metadata: Document metadata
            
        Returns:
            Dictionary with metadata embedding
        """
        try:
            # Create a text representation of the metadata
            metadata_text = self._create_metadata_text(metadata)
            
            # Generate embedding
            embedding = await self.embedding_model.create_embedding(metadata_text)
            
            metadata_embedding = {
                'embedding': embedding,
                'metadata': {
                    'person_name': metadata.get('person_name', ''),
                    'topics': metadata.get('topics', []),
                    'keywords': metadata.get('keywords', []),
                    'entities': metadata.get('entities', {}),
                    'summary': metadata.get('summary', '')
                }
            }
            
            return metadata_embedding
            
        except Exception as e:
            logger.error(f"Error generating metadata embedding: {e}")
            return {}
    
    def _create_metadata_text(self, metadata: Dict) -> str:
        """
        Create a text representation of metadata for embedding.
        
        Args:
            metadata: Document metadata
            
        Returns:
            Text representation
        """
        parts = []
        
        # Add person name
        if metadata.get('person_name'):
            parts.append(f"Person: {metadata['person_name']}")
        
        # Add topics
        if metadata.get('topics'):
            parts.append(f"Topics: {', '.join(metadata['topics'])}")
        
        # Add keywords
        if metadata.get('keywords'):
            parts.append(f"Keywords: {', '.join(metadata['keywords'])}")
        
        # Add entities
        if metadata.get('entities'):
            entities_parts = []
            for entity_type, entity_list in metadata['entities'].items():
                if entity_list:
                    entities_parts.append(f"{entity_type}: {', '.join(entity_list)}")
            
            if entities_parts:
                parts.append("Entities:\n" + "\n".join(entities_parts))
        
        # Add summary
        if metadata.get('summary'):
            parts.append(f"Summary: {metadata['summary']}")
        
        return "\n\n".join(parts)
