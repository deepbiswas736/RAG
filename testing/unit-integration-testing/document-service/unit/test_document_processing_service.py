"""
Unit tests for Document Processing Service
"""

import pytest
import sys
import os
import io
from unittest.mock import patch, MagicMock, AsyncMock
from typing import Tuple, Optional

# Add the microservices directory to the Python path
sys.path.append(os.path.abspath("microservices/document-service/app"))

from domain.services.document_processing_service import DocumentProcessingService


class TestDocumentProcessingService:
    """Tests for DocumentProcessingService"""
    
    @pytest.fixture
    def processing_service(self):
        """Fixture for creating a document processing service"""
        return DocumentProcessingService()
    
    @patch("domain.services.document_processing_service.subprocess.run")
    def test_extract_text_from_pdf(self, mock_run, processing_service):
        """Test extracting text from PDF"""
        # Mock subprocess response
        mock_run.return_value = MagicMock(
            stdout=b"This is the extracted text from the PDF",
            stderr=b"",
            returncode=0
        )
        
        # Test data
        pdf_content = b"%PDF-1.7\nTest PDF"
        
        # Extract text
        text, error = processing_service._extract_text_from_pdf(pdf_content)
        
        # Check result
        assert text == "This is the extracted text from the PDF"
        assert error is None
        
        # Verify subprocess was called
        mock_run.assert_called_once()
        
    @patch("domain.services.document_processing_service.subprocess.run")
    def test_extract_text_from_pdf_error(self, mock_run, processing_service):
        """Test error handling when extracting text"""
        # Mock subprocess response with error
        mock_run.return_value = MagicMock(
            stdout=b"",
            stderr=b"Error: Invalid PDF format",
            returncode=1
        )
        
        # Test data
        pdf_content = b"Invalid PDF content"
        
        # Extract text
        text, error = processing_service._extract_text_from_pdf(pdf_content)
        
        # Check result
        assert text is None
        assert error == "Error: Invalid PDF format"
        
        # Verify subprocess was called
        mock_run.assert_called_once()
        
    @patch("domain.services.document_processing_service.subprocess.run")
    def test_convert_to_pdf(self, mock_run, processing_service):
        """Test converting a document to PDF"""
        # Mock subprocess response
        mock_run.return_value = MagicMock(
            stdout=b"%PDF-1.7\nConverted PDF content",
            stderr=b"",
            returncode=0
        )
        
        # Test data
        doc_content = b"Original document content"
        
        # Convert to PDF
        pdf_content, error = processing_service.convert_to_pdf(
            content=doc_content,
            file_name="test.docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        
        # Check result
        assert pdf_content == b"%PDF-1.7\nConverted PDF content"
        assert error is None
        
        # Verify subprocess was called
        mock_run.assert_called_once()
        
    @patch("domain.services.document_processing_service.subprocess.run")
    def test_convert_to_pdf_error(self, mock_run, processing_service):
        """Test error handling during PDF conversion"""
        # Mock subprocess response with error
        mock_run.return_value = MagicMock(
            stdout=b"",
            stderr=b"Error: Cannot convert file",
            returncode=1
        )
        
        # Test data
        doc_content = b"Original document content"
        
        # Convert to PDF
        pdf_content, error = processing_service.convert_to_pdf(
            content=doc_content,
            file_name="test.docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        
        # Check result
        assert pdf_content is None
        assert error == "Error: Cannot convert file"
        
        # Verify subprocess was called
        mock_run.assert_called_once()
        
    @patch("domain.services.document_processing_service.DocumentProcessingService._extract_text_from_pdf")
    def test_process_document_pdf(self, mock_extract_text, processing_service):
        """Test processing a PDF document"""
        # Mock extract text response
        mock_extract_text.return_value = ("This is the extracted text", None)
        
        # Test data
        doc_content = b"%PDF-1.7\nTest PDF"
        
        # Process document
        text, metadata, error = processing_service.process_document(
            content=doc_content,
            file_name="test.pdf",
            content_type="application/pdf"
        )
        
        # Check result
        assert text == "This is the extracted text"
        assert metadata == {}
        assert error is None
        
        # Verify extract_text was called
        mock_extract_text.assert_called_once_with(doc_content)
        
    @patch("domain.services.document_processing_service.DocumentProcessingService.convert_to_pdf")
    @patch("domain.services.document_processing_service.DocumentProcessingService._extract_text_from_pdf")
    def test_process_document_docx(self, mock_extract_text, mock_convert_to_pdf, processing_service):
        """Test processing a Word document"""
        # Mock convert_to_pdf response
        mock_convert_to_pdf.return_value = (b"%PDF-1.7\nConverted PDF", None)
        
        # Mock extract_text response
        mock_extract_text.return_value = ("This is the extracted text", None)
        
        # Test data
        doc_content = b"Original document content"
        
        # Process document
        text, metadata, error = processing_service.process_document(
            content=doc_content,
            file_name="test.docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        
        # Check result
        assert text == "This is the extracted text"
        assert metadata == {}
        assert error is None
        
        # Verify mocks were called
        mock_convert_to_pdf.assert_called_once_with(
            doc_content,
            "test.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        mock_extract_text.assert_called_once_with(b"%PDF-1.7\nConverted PDF")
        
    @patch("domain.services.document_processing_service.DocumentProcessingService.convert_to_pdf")
    def test_process_document_conversion_error(self, mock_convert_to_pdf, processing_service):
        """Test handling conversion errors during document processing"""
        # Mock convert_to_pdf response with error
        mock_convert_to_pdf.return_value = (None, "Conversion failed")
        
        # Test data
        doc_content = b"Original document content"
        
        # Process document
        text, metadata, error = processing_service.process_document(
            content=doc_content,
            file_name="test.docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        
        # Check result
        assert text is None
        assert metadata == {}
        assert error == "Conversion failed"
        
        # Verify mock was called
        mock_convert_to_pdf.assert_called_once()
        
    def test_process_document_unsupported_type(self, processing_service):
        """Test processing an unsupported document type"""
        # Test data
        doc_content = b"Original document content"
        
        # Process document
        text, metadata, error = processing_service.process_document(
            content=doc_content,
            file_name="test.xyz",
            content_type="application/octet-stream"
        )
        
        # Check result
        assert text is None
        assert metadata == {}
        assert error == "Unsupported file type: application/octet-stream"
        
    def test_process_document_plain_text(self, processing_service):
        """Test processing a plain text document"""
        # Test data
        text_content = b"This is a plain text document"
        
        # Process document
        text, metadata, error = processing_service.process_document(
            content=text_content,
            file_name="test.txt",
            content_type="text/plain"
        )
        
        # Check result
        assert text == "This is a plain text document"
        assert metadata == {}
        assert error is None
        
    @patch("domain.services.document_processing_service.json.loads")
    def test_process_document_json(self, mock_json_loads, processing_service):
        """Test processing a JSON document"""
        # Mock json.loads
        mock_json_loads.return_value = {"title": "Test", "content": "This is JSON content"}
        
        # Test data
        json_content = b'{"title": "Test", "content": "This is JSON content"}'
        
        # Process document
        text, metadata, error = processing_service.process_document(
            content=json_content,
            file_name="test.json",
            content_type="application/json"
        )
        
        # Check result
        assert "This is JSON content" in text
        assert "Test" in text
        assert metadata == {"title": "Test", "content": "This is JSON content"}
        assert error is None
        
        # Verify mock was called
        mock_json_loads.assert_called_once()
        
    @patch("domain.services.document_processing_service.json.loads")
    def test_process_document_json_error(self, mock_json_loads, processing_service):
        """Test handling JSON parsing errors"""
        # Mock json.loads to raise an exception
        mock_json_loads.side_effect = Exception("Invalid JSON")
        
        # Test data
        json_content = b'{"title": "Test", "content": Invalid JSON}'
        
        # Process document
        text, metadata, error = processing_service.process_document(
            content=json_content,
            file_name="test.json",
            content_type="application/json"
        )
        
        # Check result
        assert text is None
        assert metadata == {}
        assert "Failed to parse JSON" in error
        
        # Verify mock was called
        mock_json_loads.assert_called_once()
