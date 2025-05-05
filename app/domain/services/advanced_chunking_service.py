import re
import logging
from typing import List, Dict, Any, Optional
import nltk
from nltk.tokenize import sent_tokenize

logger = logging.getLogger(__name__)

class ChunkingStrategy:
    """Base class for document chunking strategies"""
    
    def chunk_text(self, text: str) -> List[str]:
        """Split text into chunks according to the strategy"""
        raise NotImplementedError("Subclasses must implement chunk_text")


class AdvancedChunkingService:
    """
    Advanced document chunking service that uses semantic boundaries
    and contextual awareness for improved retrieval quality.
    """
    
    def __init__(self):
        # Initialize NLTK resources if needed
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            try:
                nltk.download('punkt', quiet=True)
                logger.info("Downloaded NLTK punkt tokenizer")
            except Exception as e:
                logger.warning(f"Failed to download NLTK resources: {e}")
    
    async def chunk_document(
        self, 
        text: str, 
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        respect_semantic_boundaries: bool = True
    ) -> List[str]:
        """
        Split document into semantically meaningful chunks.
        
        Args:
            text: Document text to chunk
            chunk_size: Target chunk size in characters
            chunk_overlap: Overlap between chunks in characters
            respect_semantic_boundaries: Whether to respect paragraph and sentence boundaries
            
        Returns:
            List of text chunks
        """
        if not text:
            return []
            
        # Normalize line breaks
        text = self._normalize_text(text)
        
        if respect_semantic_boundaries:
            return self._chunk_with_semantic_boundaries(text, chunk_size, chunk_overlap)
        else:
            return self._simple_chunk(text, chunk_size, chunk_overlap)
    
    def _normalize_text(self, text: str) -> str:
        """Clean and normalize text for processing"""
        # Replace multiple newlines with a single one
        text = re.sub(r'\n+', '\n', text)
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _simple_chunk(self, text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
        """Simple overlapping chunk strategy without respecting semantic boundaries"""
        chunks = []
        start = 0
        text_len = len(text)
        
        while start < text_len:
            end = min(start + chunk_size, text_len)
            
            # If this is not the first chunk and not the end of the text
            if start > 0 and end < text_len:
                # Try to find a space to break at
                space_pos = text.rfind(" ", start, end)
                if space_pos > start:
                    end = space_pos
            
            chunks.append(text[start:end].strip())
            start = end - chunk_overlap if end < text_len else text_len
        
        return chunks
    
    def _chunk_with_semantic_boundaries(
        self, 
        text: str, 
        chunk_size: int, 
        chunk_overlap: int
    ) -> List[str]:
        """Chunk text respecting paragraph and sentence boundaries"""
        # Split by paragraphs first
        paragraphs = text.split("\n")
        
        chunks = []
        current_chunk = ""
        
        for paragraph in paragraphs:
            if not paragraph.strip():
                continue
                
            # If adding this paragraph exceeds the chunk size
            if len(current_chunk) + len(paragraph) > chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                
                # If the paragraph itself is too large, split into sentences
                if len(paragraph) > chunk_size:
                    sentences = sent_tokenize(paragraph)
                    sentence_chunk = ""
                    
                    for sentence in sentences:
                        if len(sentence_chunk) + len(sentence) > chunk_size:
                            if sentence_chunk:
                                chunks.append(sentence_chunk.strip())
                            sentence_chunk = sentence
                        else:
                            sentence_chunk += " " + sentence if sentence_chunk else sentence
                    
                    if sentence_chunk:
                        current_chunk = sentence_chunk
                else:
                    current_chunk = paragraph
            else:
                current_chunk += " " + paragraph if current_chunk else paragraph
        
        if current_chunk:
            chunks.append(current_chunk.strip())
            
        # Apply overlap
        if chunk_overlap > 0:
            overlapped_chunks = []
            for i in range(len(chunks)):
                if i > 0:
                    # Get sentences from previous chunk's end
                    prev_sentences = sent_tokenize(chunks[i-1])
                    overlap_sentences = prev_sentences[-3:] if len(prev_sentences) > 3 else prev_sentences
                    
                    # Add overlapping content from previous chunk
                    overlap_text = " ".join(overlap_sentences)
                    if len(overlap_text) > chunk_overlap:
                        overlap_text = overlap_text[-chunk_overlap:]
                    
                    overlapped_chunks.append(overlap_text + " " + chunks[i])
                else:
                    overlapped_chunks.append(chunks[i])
                    
            return overlapped_chunks
            
        return chunks