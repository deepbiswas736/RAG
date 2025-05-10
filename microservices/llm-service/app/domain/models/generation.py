"""
LLM Generation Response Models
-----------------------------
Domain models for LLM text generation responses
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Any
from datetime import datetime


@dataclass
class GenerationResponse:
    """Model representing an LLM generation response"""
    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    elapsed_time: float
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            "text": self.text,
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "elapsed_time": self.elapsed_time,
            "created_at": self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GenerationResponse':
        """Create from dictionary representation"""
        created_at = data.get("created_at")
        if created_at and isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        
        return cls(
            text=data["text"],
            model=data["model"],
            prompt_tokens=data["prompt_tokens"],
            completion_tokens=data["completion_tokens"],
            total_tokens=data["total_tokens"],
            elapsed_time=data["elapsed_time"],
            created_at=created_at
        )


@dataclass
class StreamingChunk:
    """Model representing a chunk in a streaming LLM response"""
    text: str
    model: str
    is_final: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            "text": self.text,
            "model": self.model,
            "is_final": self.is_final
        }
