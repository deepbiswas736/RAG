"""
Test Client for Metadata Extraction

A simple FastAPI app to test the metadata extraction service.
"""

import os
import logging
import asyncio
import aiohttp
import json
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
import uuid
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="Metadata Extraction Test Client")

# Configuration from environment variables
DOCUMENT_SERVICE_URL = os.getenv("DOCUMENT_SERVICE_URL", "http://localhost:8000")
LLM_SERVICE_URL = os.getenv("LLM_SERVICE_URL", "http://localhost:8001")
TEST_DOCUMENT_PATH = os.getenv("TEST_DOCUMENT_PATH", "/test_data")

# DTO Models
class DocumentDTO(BaseModel):
    id: str
    name: str
    file_type: str
    file_size: int
    content_type: str
    status: str
    created_at: str
    metadata: Optional[Dict[str, Any]] = None

class MetadataStatusResponse(BaseModel):
    document_id: str
    status: str
    metadata: Optional[Dict[str, Any]] = None
    extraction_requested_at: str
    last_checked_at: str
    checks_count: int

# In-memory storage for tracking metadata extraction requests
metadata_requests: Dict[str, Dict[str, Any]] = {}

@app.get("/")
async def root():
    """Root endpoint."""
    return {"status": "ok", "service": "Metadata Extraction Test Client"}

@app.post("/documents", response_model=DocumentDTO)
async def upload_document(
    file: UploadFile = File(...),
    extract_metadata: bool = Form(True)
):
    """Upload a document and optionally trigger metadata extraction."""
    try:
        # Step 1: Upload document to the Document Service
        document = await _upload_to_document_service(file)
        document_id = document["id"]
        
        # Step 2: Optionally trigger metadata extraction
        if extract_metadata:
            logger.info(f"Requesting metadata extraction for document {document_id}")
            await _request_metadata_extraction(document_id)
            
            # Track the request for status checking
            metadata_requests[document_id] = {
                "document_id": document_id,
                "status": "requested",
                "extraction_requested_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "last_checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "checks_count": 0
            }
        
        return document
    
    except Exception as e:
        logger.error(f"Error processing document: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing document: {str(e)}")

@app.get("/status/{document_id}", response_model=MetadataStatusResponse)
async def check_metadata_status(document_id: str):
    """Check the status of metadata extraction for a document."""
    try:
        # Check if we're tracking this document
        if document_id not in metadata_requests:
            raise HTTPException(status_code=404, detail=f"Document {document_id} not found in tracking")
        
        # Update tracking info
        metadata_requests[document_id]["last_checked_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        metadata_requests[document_id]["checks_count"] += 1
        
        # Get the current document metadata from the Document Service
        document = await _get_document(document_id)
        
        # Update status based on metadata
        if document.get("metadata", {}).get("extracted_metadata"):
            metadata_requests[document_id]["status"] = "completed"
            metadata_requests[document_id]["metadata"] = document.get("metadata")
        elif document.get("metadata", {}).get("error"):
            metadata_requests[document_id]["status"] = "failed"
            metadata_requests[document_id]["metadata"] = {
                "error": document.get("metadata", {}).get("error")
            }
        
        return metadata_requests[document_id]
    
    except Exception as e:
        logger.error(f"Error checking metadata status: {e}")
        raise HTTPException(status_code=500, detail=f"Error checking status: {str(e)}")

@app.get("/documents", response_model=List[DocumentDTO])
async def list_documents():
    """List all documents in the Document Service."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{DOCUMENT_SERVICE_URL}/documents") as response:
                if response.status != 200:
                    text = await response.text()
                    raise Exception(f"Failed to list documents: {text}")
                
                data = await response.json()
                return data.get("documents", [])
    
    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        raise HTTPException(status_code=500, detail=f"Error listing documents: {str(e)}")

@app.get("/llm/status")
async def check_llm_status():
    """Check the status of the LLM service and metadata consumer."""
    try:
        # Check LLM service health
        llm_health = await _check_llm_health()
        
        # Check metadata consumer status
        metadata_status = await _check_metadata_consumer()
        
        return {
            "llm_service": llm_health,
            "metadata_consumer": metadata_status
        }
    
    except Exception as e:
        logger.error(f"Error checking LLM status: {e}")
        raise HTTPException(status_code=500, detail=f"Error checking LLM status: {str(e)}")

# Helper functions
async def _upload_to_document_service(file: UploadFile) -> Dict[str, Any]:
    """Upload a file to the Document Service."""
    async with aiohttp.ClientSession() as session:
        form_data = aiohttp.FormData()
        form_data.add_field('file', file.file.read(), 
                          filename=file.filename,
                          content_type=file.content_type)
        
        async with session.post(f"{DOCUMENT_SERVICE_URL}/documents", data=form_data) as response:
            if response.status != 200:
                text = await response.text()
                raise Exception(f"Failed to upload document: {text}")
            
            return await response.json()

async def _request_metadata_extraction(document_id: str) -> bool:
    """Request metadata extraction for a document."""
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{DOCUMENT_SERVICE_URL}/documents/{document_id}/extract-metadata"
        ) as response:
            if response.status != 200:
                text = await response.text()
                raise Exception(f"Failed to request metadata extraction: {text}")
            
            return True

async def _get_document(document_id: str) -> Dict[str, Any]:
    """Get document details from the Document Service."""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{DOCUMENT_SERVICE_URL}/documents/{document_id}") as response:
            if response.status != 200:
                text = await response.text()
                raise Exception(f"Failed to get document: {text}")
            
            return await response.json()

async def _check_llm_health() -> Dict[str, Any]:
    """Check the health of the LLM service."""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{LLM_SERVICE_URL}/health") as response:
            if response.status != 200:
                return {"status": "unavailable", "code": response.status}
            
            return await response.json()

async def _check_metadata_consumer() -> Dict[str, Any]:
    """Check the status of the metadata consumer."""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{LLM_SERVICE_URL}/metadata/status") as response:
            if response.status != 200:
                return {"status": "unavailable", "code": response.status}
            
            return await response.json()
