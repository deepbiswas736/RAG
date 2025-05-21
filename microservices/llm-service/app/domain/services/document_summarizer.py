"""
Document Summarizer
-----------------
Service to generate summaries and extract metadata from documents
"""

import logging
import re
import json
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class DocumentSummarizer:
    """Service for generating document summaries and extracting metadata"""
    
    def __init__(self, llm_service):
        """
        Initialize the Document Summarizer
        
        Args:
            llm_service: LLM service for text generation
        """
        self.llm_service = llm_service
        
    async def generate_document_summary(self, document_content: str, file_type: str, max_tokens: int = 150) -> Dict[str, Any]:
        """
        Generate a summary and extract metadata from document content
        
        Args:
            document_content: Document content text
            file_type: Type of document file
            max_tokens: Maximum tokens for LLM response
            
        Returns:
            Dictionary with document summary metadata
        """
        # Handle empty content case
        if not document_content:
            logger.warning("Cannot generate summary for empty document content")
            return {"description": "No content available", "category": "unknown", "related_entity": "N/A"}
        
        # Create recursive summary for long documents
        summary_prompt = self._create_document_summary_prompt(document_content, file_type)
        
        # Generate summary using LLM
        try:
            summary_text = await self.llm_service.generate_text(
                prompt=summary_prompt,
                temperature=0.3,
                max_tokens=max_tokens
            )
            
            # Parse summary from LLM response
            parsed_summary = self._parse_document_summary_from_llm_output(summary_text)
            logger.info(f"Generated document summary: {parsed_summary.get('description')[:50]}...")
            return parsed_summary
            
        except Exception as e:
            logger.error(f"Error generating document summary: {e}")
            return {"description": f"Error generating summary: {str(e)}", 
                   "category": "unknown", 
                   "related_entity": "N/A"}
    
    async def generate_recursive_summary(self, document_content: str, file_type: str, 
                                       chunk_size: int = 2000, 
                                       max_tokens: int = 150) -> Dict[str, Any]:
        """
        Generate summary for large documents by recursively splitting and summarizing
        
        Args:
            document_content: Document content text
            file_type: Type of document file
            chunk_size: Size of each content chunk for summarization
            max_tokens: Maximum tokens for LLM response
            
        Returns:
            Dictionary with document summary metadata
        """
        # If content is small enough, summarize directly
        if len(document_content) <= chunk_size:
            return await self.generate_document_summary(document_content, file_type, max_tokens)
        
        # Split into chunks and summarize each
        chunks = [document_content[i:i+chunk_size] for i in range(0, len(document_content), chunk_size)]
        logger.info(f"Document content too large, splitting into {len(chunks)} chunks for recursive summarization")
        
        # Generate summaries for each chunk
        chunk_summaries = []
        for i, chunk in enumerate(chunks):
            try:
                summary = await self.generate_document_summary(
                    f"DOCUMENT PART {i+1} of {len(chunks)}: {chunk}", 
                    file_type,
                    max_tokens=100
                )
                chunk_summaries.append(summary.get("description", ""))
            except Exception as e:
                logger.error(f"Error summarizing chunk {i+1}: {e}")
        
        # Combine chunk summaries into a single document
        combined_summary = " ".join(chunk_summaries)
        
        # Generate final summary from the combined summaries
        final_prompt = f"""Based on these summaries from different parts of the document, provide a unified description, category, and related entity:

Document Summaries:
{combined_summary}

Return the information in a structured JSON format:
```json
{{
  "description": "Concise description of the document's purpose.",
  "category": "Document category (e.g., resume, invoice, property_tax_document, financial_report, etc.).",
  "related_entity": "The main person, organization, or item this document is about. Use 'N/A' if not applicable."
}}
```"""

        try:
            final_summary_text = await self.llm_service.generate_text(
                prompt=final_prompt,
                temperature=0.3,
                max_tokens=max_tokens
            )
            
            return self._parse_document_summary_from_llm_output(final_summary_text)
        except Exception as e:
            logger.error(f"Error generating final summary: {e}")
            return {"description": " ".join(chunk_summaries[:3]) + "...", 
                   "category": "unknown", 
                   "related_entity": "N/A"}
    
    def _create_document_summary_prompt(self, document_content: str, file_type: str) -> str:
        """
        Create a prompt for summarizing the document's purpose and category
        
        Args:
            document_content: Document content text
            file_type: Type of document file
            
        Returns:
            Prompt text for LLM
        """
        # Limit content length for the prompt
        preview_content = document_content[:2000]

        return f"""Analyze the following document content (and file type '{file_type}') to determine its primary purpose and category.
Provide a concise description, identify the main category (e.g., 'resume', 'invoice', 'property_tax_document', 'legal_agreement', 'research_paper', 'other'), and if applicable, the primary entity it relates to (e.g., a person's name, a company name, a property address).

Document content preview:
{preview_content}
...

Return the information in a structured JSON format:
```json
{{
  "description": "Concise description of the document's purpose (e.g., Resume of John Doe, Property tax statement for 123 Main St, Q3 Financial Report for Acme Corp).",
  "category": "Document category (e.g., resume, invoice, property_tax_document, financial_report, legal_agreement, correspondence, other).",
  "related_entity": "The main person, organization, or item this document is about (e.g., John Doe, Acme Corp, 123 Main St). If not applicable, use 'N/A'."
}}
```
"""

    def _parse_document_summary_from_llm_output(self, llm_output: str) -> Dict[str, Any]:
        """
        Parse the document summary, category, and related entity from LLM output
        
        Args:
            llm_output: Text output from LLM
            
        Returns:
            Dictionary with parsed summary metadata
        """
        try:
            json_match = re.search(r'```json\s*(.*?)\s*```', llm_output, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                data = json.loads(json_str)
                return {
                    "description": data.get("description", "N/A"),
                    "category": data.get("category", "other"),
                    "related_entity": data.get("related_entity", "N/A")
                }
            
            # If no JSON found, try to extract information from text
            logger.warning(f"Could not parse JSON summary from LLM output, trying text extraction")
            
            description = "N/A"
            category = "unknown"
            entity = "N/A"
            
            # Simple extraction based on common patterns
            if "description:" in llm_output.lower():
                description_match = re.search(r'description:(.+?)(?=category:|related_entity:|$)', llm_output, re.IGNORECASE | re.DOTALL)
                if description_match:
                    description = description_match.group(1).strip()
            
            if "category:" in llm_output.lower():
                category_match = re.search(r'category:(.+?)(?=description:|related_entity:|$)', llm_output, re.IGNORECASE | re.DOTALL)
                if category_match:
                    category = category_match.group(1).strip()
            
            if "related_entity:" in llm_output.lower() or "entity:" in llm_output.lower():
                entity_match = re.search(r'(?:related_)?entity:(.+?)(?=description:|category:|$)', llm_output, re.IGNORECASE | re.DOTALL)
                if entity_match:
                    entity = entity_match.group(1).strip()
            
            return {"description": description, "category": category, "related_entity": entity}
            
        except Exception as e:
            logger.error(f"Error parsing document summary from LLM output: {e}. Output: {llm_output}")
            return {"description": "Error in parsing summary", "category": "unknown", "related_entity": "N/A"}
