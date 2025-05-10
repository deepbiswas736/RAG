"""
Query Response Domain Model
--------------------------
Core domain model for representing responses to user queries
"""

from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from uuid import uuid4


@dataclass(frozen=True)
class ResponseId:
    """Value object for response ID"""
    value: str

    @classmethod
    def create_new(cls) -> "ResponseId":
        """Create a new response ID"""
        return cls(value=str(uuid4()))


@dataclass
class DocumentReference:
    """Reference to a document used as context"""
    document_id: str
    title: Optional[str] = None
    source: Optional[str] = None
    page: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    relevance_score: Optional[float] = None
    content_excerpt: Optional[str] = None


@dataclass
class QueryResponse:
    """
    Domain entity representing a response to a user query
    """
    id: ResponseId
    query_id: str
    text: str
    created_at: datetime = field(default_factory=datetime.now)
    references: List[DocumentReference] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Model information
    model: Optional[str] = None
    
    # Performance metrics
    latency: Optional[float] = None  # processing time in seconds
    token_usage: Dict[str, int] = field(default_factory=dict)

    @classmethod
    def create(cls, 
              query_id: str,
              text: str,
              references: Optional[List[DocumentReference]] = None,
              model: Optional[str] = None,
              latency: Optional[float] = None,
              token_usage: Optional[Dict[str, int]] = None) -> "QueryResponse":
        """
        Create a new query response
        
        Args:
            query_id: ID of the query this is responding to
            text: The response text
            references: Optional list of document references
            model: Optional name of the LLM model used
            latency: Optional processing time in seconds
            token_usage: Optional token usage statistics
            
        Returns:
            A new QueryResponse instance
        """
        return cls(
            id=ResponseId.create_new(),
            query_id=query_id,
            text=text,
            references=references or [],
            model=model,
            latency=latency,
            token_usage=token_usage or {},
        )
    
    def add_reference(self, reference: DocumentReference) -> None:
        """
        Add a document reference to the response
        
        Args:
            reference: Document reference to add
        """
        self.references.append(reference)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            "id": self.id.value,
            "query_id": self.query_id,
            "text": self.text,
            "created_at": self.created_at.isoformat(),
            "references": [
                {
                    "document_id": ref.document_id,
                    "title": ref.title,
                    "source": ref.source,
                    "page": ref.page,
                    "metadata": ref.metadata,
                    "relevance_score": ref.relevance_score,
                    "content_excerpt": ref.content_excerpt,
                }
                for ref in self.references
            ],
            "metadata": self.metadata,
            "model": self.model,
            "latency": self.latency,
            "token_usage": self.token_usage,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QueryResponse":
        """Create from dictionary representation"""
        return cls(
            id=ResponseId(value=data["id"]),
            query_id=data["query_id"],
            text=data["text"],
            created_at=datetime.fromisoformat(data["created_at"]),
            references=[
                DocumentReference(
                    document_id=ref["document_id"],
                    title=ref.get("title"),
                    source=ref.get("source"),
                    page=ref.get("page"),
                    metadata=ref.get("metadata", {}),
                    relevance_score=ref.get("relevance_score"),
                    content_excerpt=ref.get("content_excerpt"),
                )
                for ref in data.get("references", [])
            ],
            metadata=data.get("metadata", {}),
            model=data.get("model"),
            latency=data.get("latency"),
            token_usage=data.get("token_usage", {}),
        )
