"""
Chunking Service
--------------
Handles breaking documents into smaller, manageable chunks for embedding and retrieval.
"""

import logging
import re
from typing import List, Dict, Any, Optional, Union
import numpy as np

logger = logging.getLogger(__name__)

class ChunkingService:
    """
    Service for chunking documents into smaller pieces for processing
    and retrieval in a RAG system
    """
    
    def __init__(
        self,
        default_chunk_size: int = 1000,
        default_chunk_overlap: int = 200,
        min_chunk_size: int = 100,
        max_chunk_size: int = 2000
    ):
        """
        Initialize the chunking service with default parameters
        
        Args:
            default_chunk_size: Default size of each chunk in characters
            default_chunk_overlap: Default overlap between chunks in characters
            min_chunk_size: Minimum allowed chunk size
            max_chunk_size: Maximum allowed chunk size
        """
        self.default_chunk_size = default_chunk_size
        self.default_chunk_overlap = default_chunk_overlap
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        
    def chunk_text(
        self,
        text: str,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Split text into overlapping chunks
        
        Args:
            text: The text to split
            chunk_size: Size of each chunk in characters
            chunk_overlap: Overlap between chunks in characters
            metadata: Additional metadata to include with each chunk
            
        Returns:
            List of chunk dictionaries with text and metadata
        """
        # Use default values if not provided
        chunk_size = chunk_size or self.default_chunk_size
        chunk_overlap = chunk_overlap or self.default_chunk_overlap
        
        # Validate chunk size and overlap
        if chunk_size > self.max_chunk_size:
            logger.warning(f"Chunk size {chunk_size} exceeds maximum {self.max_chunk_size}. Using maximum.")
            chunk_size = self.max_chunk_size
            
        if chunk_size < self.min_chunk_size:
            logger.warning(f"Chunk size {chunk_size} below minimum {self.min_chunk_size}. Using minimum.")
            chunk_size = self.min_chunk_size
            
        if chunk_overlap >= chunk_size:
            logger.warning(f"Overlap {chunk_overlap} >= chunk size {chunk_size}. Setting to half of chunk size.")
            chunk_overlap = chunk_size // 2
            
        # Clean up the text - remove excessive newlines and whitespace
        text = self._clean_text(text)
            
        # If text is empty after cleaning, return empty list
        if not text or len(text.strip()) == 0:
            return []
            
        # Initialize chunks
        chunks = []
        
        # Split text into paragraphs based on double newlines
        paragraphs = text.split("\n\n")
        paragraphs = [p for p in paragraphs if p.strip()]
        
        # Initialize current chunk
        current_chunk = ""
        current_paragraphs = []
        
        # Process paragraphs
        for i, paragraph in enumerate(paragraphs):
            # If adding this paragraph would exceed chunk size and we already have content,
            # finalize the current chunk and start a new one
            if len(current_chunk) + len(paragraph) > chunk_size and current_chunk:
                # Create chunk with metadata
                chunk_data = {
                    "text": current_chunk.strip(),
                    "metadata": self._create_chunk_metadata(
                        metadata or {},
                        chunk_index=len(chunks),
                        paragraphs=current_paragraphs
                    )
                }
                chunks.append(chunk_data)
                
                # Start new chunk with overlap from previous chunk
                overlap_size = 0
                overlap_paragraphs = []
                new_chunk = ""
                
                # Add paragraphs from the end until we reach the desired overlap
                for p in reversed(current_paragraphs):
                    if overlap_size + len(p) <= chunk_overlap:
                        new_chunk = p + "\n\n" + new_chunk
                        overlap_paragraphs.insert(0, p)
                        overlap_size += len(p) + 2  # +2 for newlines
                    else:
                        # If adding full paragraph exceeds overlap, add partial paragraph
                        remain = chunk_overlap - overlap_size
                        if remain > 0:
                            partial = p[-remain:]
                            new_chunk = partial + new_chunk
                        break
                
                current_chunk = new_chunk
                current_paragraphs = overlap_paragraphs
            
            # Add current paragraph to the chunk
            current_chunk += paragraph + "\n\n"
            current_paragraphs.append(paragraph)
        
        # Don't forget the last chunk if it has content
        if current_chunk.strip():
            chunk_data = {
                "text": current_chunk.strip(),
                "metadata": self._create_chunk_metadata(
                    metadata or {}, 
                    chunk_index=len(chunks),
                    paragraphs=current_paragraphs
                )
            }
            chunks.append(chunk_data)
        
        return chunks
    
    def _clean_text(self, text: str) -> str:
        """
        Clean text by removing excessive whitespace and normalizing newlines
        
        Args:
            text: The text to clean
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        # Replace multiple newlines with double newline
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Replace multiple spaces with single space
        text = re.sub(r' {2,}', ' ', text)
        
        return text.strip()
    
    def _create_chunk_metadata(
        self,
        base_metadata: Dict[str, Any],
        chunk_index: int,
        paragraphs: List[str]
    ) -> Dict[str, Any]:
        """
        Create metadata for a chunk
        
        Args:
            base_metadata: Base metadata to include
            chunk_index: Index of the chunk
            paragraphs: List of paragraphs in the chunk
            
        Returns:
            Metadata dictionary
        """
        # Create a copy of the base metadata
        metadata = {**base_metadata}
        
        # Add chunk-specific metadata
        metadata.update({
            "chunk_index": chunk_index,
            "paragraph_count": len(paragraphs),
            "word_count": sum(len(p.split()) for p in paragraphs),
            "char_count": sum(len(p) for p in paragraphs)
        })
        
        return metadata
    
    def chunk_with_semantic_boundaries(
        self,
        text: str,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Advanced chunking that tries to respect semantic boundaries like headers,
        paragraphs, and sentences.
        
        Args:
            text: The text to split
            chunk_size: Size of each chunk in characters
            chunk_overlap: Overlap between chunks in characters
            metadata: Additional metadata to include with each chunk
            
        Returns:
            List of chunk dictionaries with text and metadata
        """
        # Use default values if not provided
        chunk_size = chunk_size or self.default_chunk_size
        chunk_overlap = chunk_overlap or self.default_chunk_overlap
        
        # First detect section headers (advanced)
        # Look for patterns like "Chapter X", "Section X", numbered sections, etc.
        section_pattern = r'(?:^|\n)(?:#{1,6}|(?:CHAPTER|Chapter|Section|SECTION|Part|PART)\s+[\dIVXLC]+:?)'
        
        # Split by potential section headers
        sections = re.split(f'({section_pattern})', text)
        
        # Recombine headers with their content
        processed_sections = []
        i = 0
        while i < len(sections):
            if i + 1 < len(sections) and re.match(section_pattern, sections[i]):
                # It's a header, combine with the next section
                processed_sections.append(sections[i] + sections[i+1])
                i += 2
            else:
                processed_sections.append(sections[i])
                i += 1
        
        all_chunks = []
        for section in processed_sections:
            if not section.strip():
                continue
                
            # For each section, perform regular chunking
            section_chunks = self.chunk_text(
                section, 
                chunk_size=chunk_size, 
                chunk_overlap=chunk_overlap,
                metadata=metadata
            )
            
            # Add section info to metadata if possible
            section_title = self._extract_section_title(section)
            if section_title:
                for chunk in section_chunks:
                    chunk["metadata"]["section_title"] = section_title
            
            all_chunks.extend(section_chunks)
        
        # Renumber chunk indices
        for i, chunk in enumerate(all_chunks):
            chunk["metadata"]["chunk_index"] = i
        
        return all_chunks
    
    def _extract_section_title(self, section_text: str) -> Optional[str]:
        """
        Extract the title from a section
        
        Args:
            section_text: Text of the section
            
        Returns:
            Section title if found, None otherwise
        """
        # Look for the first line that might be a title
        lines = section_text.strip().split("\n")
        if not lines:
            return None
            
        first_line = lines[0].strip()
        
        # Check if it's a header style line
        if re.match(r'^#{1,6}\s+', first_line):
            # Markdown-style header, remove the #s
            return re.sub(r'^#{1,6}\s+', '', first_line)
        
        # Check for chapter/section style headers
        if re.match(r'^(?:CHAPTER|Chapter|Section|SECTION|Part|PART)\s+[\dIVXLC]+:?\s+', first_line):
            return first_line
            
        # If the first line is short, it's probably a title
        if len(first_line) < 100 and len(first_line.split()) < 15:
            return first_line
            
        return None
