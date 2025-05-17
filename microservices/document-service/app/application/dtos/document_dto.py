"""
Document DTOs
------------
Data transfer objects for document entities.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class ChunkDTO(BaseModel):
    """DTO for document chunk information"""
    id: str
    document_id: str
    chunk_index: int
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        orm_mode = True

class DocumentDTO(BaseModel):
    """DTO for document information"""
    id: str
    name: str
    file_type: str
    file_size: int 
    content_type: str
    created_at: datetime
    updated_at: datetime
    is_processed: bool
    is_chunked: bool
    processing_status: str
    processing_error: Optional[str] = None
    chunk_count: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        orm_mode = True
