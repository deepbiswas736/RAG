"""
Query Service API - Simplified Version
---------------
FastAPI implementation of the Query Service API with fixed imports
"""

import os
import logging
import json
import socket
from typing import List, Dict, Any, Optional, Union
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define API app explicitly with the name "app"
app = FastAPI(
    title="Query Service API",
    description="API for searching and retrieving information using RAG",
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
        "service": "query-service",
        "version": "1.0.0"
    }

# Define a simple root endpoint
@app.get("/")
async def root():
    return {
        "message": "Query Service is running",
        "service": "query-service",
        "version": "1.0.0"
    }
