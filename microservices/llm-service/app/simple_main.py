"""
LLM Service API - Fixed version
-------------
FastAPI implementation for the LLM service API with fixed imports
"""

import logging
import os
import sys
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import uvicorn
import json
import socket

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define API app
app = FastAPI(
    title="LLM Service API",
    description="API for LLM Services (text generation and embeddings)",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define a health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "llm-service",
        "version": "1.0.0"
    }

# Define a simple root endpoint
@app.get("/")
async def root():
    return {
        "message": "LLM Service is running",
        "service": "llm-service",
        "version": "1.0.0"
    }
