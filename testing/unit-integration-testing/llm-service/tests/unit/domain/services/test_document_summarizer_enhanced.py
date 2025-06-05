"""
Test the document summarizer functionality with different LLM response formats,
including tests for the enhanced JSON parsing functionality
"""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.domain.services.document_summarizer import DocumentSummarizer


class TestDocumentSummarizerEnhanced:
    """Test cases for the enhanced DocumentSummarizer class"""

    @pytest.fixture
    def llm_service_mock(self):
        """Create a mock LLM service"""
        llm_service = AsyncMock()
        llm_service.generate_text = AsyncMock()
        return llm_service

    @pytest.fixture
    def document_summarizer(self, llm_service_mock):
        """Create a DocumentSummarizer with mock dependencies"""
        return DocumentSummarizer(llm_service=llm_service_mock)

    def test_parse_document_summary_with_markdown_json(self, document_summarizer):
        """Test parsing document summary with JSON in markdown format"""
        # Example LLM response with markdown-formatted JSON
        llm_output = """Here's the document summary:

```json
{
  "description": "Q3 Financial Report for Acme Corp showing revenue growth",
  "category": "financial_report",
  "related_entity": "Acme Corporation"
}
```
"""
        result = document_summarizer._parse_document_summary_from_llm_output(llm_output)
        
        assert result["description"] == "Q3 Financial Report for Acme Corp showing revenue growth"
        assert result["category"] == "financial_report"
        assert result["related_entity"] == "Acme Corporation"

    def test_parse_document_summary_with_raw_json(self, document_summarizer):
        """Test parsing document summary with raw JSON (no markdown)"""
        # Example LLM response with raw JSON
        llm_output = """The document analysis is: 
{
  "description": "Resume of John Doe, Software Engineer with 5 years experience",
  "category": "resume",
  "related_entity": "John Doe"
}
"""
        result = document_summarizer._parse_document_summary_from_llm_output(llm_output)
        
        assert result["description"] == "Resume of John Doe, Software Engineer with 5 years experience"
        assert result["category"] == "resume"
        assert result["related_entity"] == "John Doe"

    def test_parse_document_summary_with_text_format(self, document_summarizer):
        """Test parsing document summary with text format"""
        # Example LLM response in plain text format
        llm_output = """
Description: Property tax statement for 123 Main St for 2024
Category: property_tax_document
Related_entity: 123 Main St
"""
        result = document_summarizer._parse_document_summary_from_llm_output(llm_output)
        
        assert result["description"] == "Property tax statement for 123 Main St for 2024"
        assert result["category"] == "property_tax_document"
        assert result["related_entity"] == "123 Main St"

    def test_parse_document_summary_with_dict_response(self, document_summarizer):
        """Test parsing document summary when LLM returns a dictionary"""
        # Example dictionary response from LLM service
        llm_output = {
            "text": """```json
{
  "description": "Invoice #12345 from ABC Suppliers",
  "category": "invoice", 
  "related_entity": "ABC Suppliers"
}
```""",
            "model": "phi",
            "prompt_tokens": 50,
            "completion_tokens": 30,
            "total_tokens": 80,
            "elapsed_time": 0.5
        }
        
        result = document_summarizer._parse_document_summary_from_llm_output(llm_output)
        
        assert result["description"] == "Invoice #12345 from ABC Suppliers"
        assert result["category"] == "invoice"
        assert result["related_entity"] == "ABC Suppliers"

    def test_parse_document_summary_with_incomplete_json(self, document_summarizer):
        """Test parsing document summary with incomplete JSON"""
        # Example LLM response with incomplete JSON
        llm_output = """```json
{
  "description": "Legal agreement between XYZ Corp and ABC Inc",
  "category": "legal_agreement",
  "related_entity": "XYZ Corp and ABC Inc"
"""  # Missing closing brace
        
        result = document_summarizer._parse_document_summary_from_llm_output(llm_output)
        
        # Should fall back to text extraction
        assert "Legal agreement" in result["description"]
        assert result["category"] != "unknown"  # Should extract from text

    def test_parse_document_summary_with_malformed_json(self, document_summarizer):
        """Test parsing document summary with malformed JSON"""
        # Example LLM response with malformed JSON (invalid syntax)
        llm_output = """```json
{
  "description": "Research paper on machine learning algorithms",
  "category": "research_paper",
  "related_entity": "University Research Team"
  "publication_date": "2024-03-15"  # Missing comma
}
```"""
        
        result = document_summarizer._parse_document_summary_from_llm_output(llm_output)
        
        # Should fall back to text extraction or simplified JSON parsing
        assert "Research paper" in result["description"] or result["description"] == "N/A"
        
    def test_parse_document_summary_with_nested_braces(self, document_summarizer):
        """Test parsing document summary with nested braces in JSON"""
        # Example LLM response with nested braces that could confuse the parser
        llm_output = """```json
{
  "description": "Contract for software development {with nested braces}",
  "category": "legal_agreement",
  "related_entity": "Tech Solutions Inc. {Software Division}"
}
```"""
        
        result = document_summarizer._parse_document_summary_from_llm_output(llm_output)
        
        assert "Contract for software development" in result["description"]
        assert result["category"] == "legal_agreement"
        assert "Tech Solutions Inc." in result["related_entity"]
        
    def test_parse_document_summary_with_dict_incomplete_json(self, document_summarizer):
        """Test parsing document summary when LLM returns a dictionary with incomplete JSON"""
        # Example dictionary response from LLM service with incomplete JSON
        llm_output = {
            "text": """{
  "description": "Medical records for patient Jane Smith",
  "category": "medical_document",
  "related_entity": "Jane Smith"
  """,  # Incomplete JSON - missing closing brace
            "model": "phi",
            "prompt_tokens": 40,
            "completion_tokens": 25,
            "total_tokens": 65,
            "elapsed_time": 0.4
        }
        
        result = document_summarizer._parse_document_summary_from_llm_output(llm_output)
        
        # Should extract information despite incomplete JSON
        assert "Medical records" in result["description"]
        assert "medical" in result["category"].lower()
        assert "Jane Smith" in result["related_entity"]
        
    def test_parse_document_summary_with_unstructured_text(self, document_summarizer):
        """Test parsing document summary with completely unstructured text"""
        llm_output = "This appears to be a legal contract between Company A and Company B dated January 15, 2024. The document outlines terms for a business partnership."
        
        result = document_summarizer._parse_document_summary_from_llm_output(llm_output)
        
        # Should return default values or extract what it can
        assert result["description"] != "Error in parsing summary"
        
    @pytest.mark.asyncio
    async def test_generate_document_summary(self, document_summarizer, llm_service_mock):
        """Test generating document summary"""
        # Mock the LLM service response
        llm_service_mock.generate_text.return_value = {
            "text": """```json
{
  "description": "Quarterly financial report for Q1 2024",
  "category": "financial_report",
  "related_entity": "Global Enterprises Inc."
}
```""",
            "model": "phi",
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "elapsed_time": 0.8
        }
        
        result = await document_summarizer.generate_document_summary(
            "Financial data for first quarter...", "pdf", 100
        )
        
        assert result["description"] == "Quarterly financial report for Q1 2024"
        assert result["category"] == "financial_report"
        assert result["related_entity"] == "Global Enterprises Inc."
        
        # Verify LLM service was called correctly
        llm_service_mock.generate_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_document_summary_with_error(self, document_summarizer, llm_service_mock):
        """Test generating document summary with error in LLM response"""
        # Mock the LLM service to raise an exception
        llm_service_mock.generate_text.side_effect = Exception("LLM service unavailable")
        
        result = await document_summarizer.generate_document_summary(
            "Some document content...", "pdf", 100
        )
        
        # Should return fallback values with error message
        assert "Error generating summary" in result["description"]
        assert result["category"] == "unknown"
        assert result["related_entity"] == "N/A"
