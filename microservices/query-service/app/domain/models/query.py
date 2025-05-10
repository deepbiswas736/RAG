"""
Query Domain Model
-----------------
Core domain model for representing user queries
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass, field
from uuid import uuid4


class QueryType(Enum):
    """Types of queries supported by the system"""
    CONVERSATIONAL = "conversational"  # Natural language conversation
    RETRIEVAL = "retrieval"            # Pure RAG retrieval
    HYBRID = "hybrid"                  # Mix of retrieval and generative
    DIRECT = "direct"                  # Direct document lookup


class QueryStatus(Enum):
    """Status of a query in the system"""
    PENDING = "pending"        # Received but not yet processed
    PROCESSING = "processing"  # Being processed
    COMPLETED = "completed"    # Processed successfully
    FAILED = "failed"          # Processing failed


@dataclass(frozen=True)
class QueryId:
    """Value object for query ID"""
    value: str

    @classmethod
    def create_new(cls) -> "QueryId":
        """Create a new query ID"""
        return cls(value=str(uuid4()))


@dataclass
class Query:
    """
    Core domain entity representing a user query
    """
    id: QueryId
    text: str
    query_type: QueryType
    status: QueryStatus = QueryStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Optional fields
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None
    
    # For conversational context
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # Filters for document retrieval
    filters: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, 
              text: str, 
              query_type: QueryType = QueryType.HYBRID,
              user_id: Optional[str] = None,
              conversation_id: Optional[str] = None,
              conversation_history: Optional[List[Dict[str, Any]]] = None,
              filters: Optional[Dict[str, Any]] = None) -> "Query":
        """
        Create a new query
        
        Args:
            text: The query text
            query_type: Type of query to perform
            user_id: Optional ID of the user making the query
            conversation_id: Optional ID of the conversation
            conversation_history: Optional history of the conversation
            filters: Optional filters to apply to document retrieval
            
        Returns:
            A new Query instance
        """
        return cls(
            id=QueryId.create_new(),
            text=text,
            query_type=query_type,
            user_id=user_id,
            conversation_id=conversation_id,
            conversation_history=conversation_history or [],
            filters=filters or {},
        )
    
    def update_status(self, status: QueryStatus) -> None:
        """
        Update the status of the query
        
        Args:
            status: New status to set
        """
        self.status = status
        self.updated_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            "id": self.id.value,
            "text": self.text,
            "query_type": self.query_type.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
            "user_id": self.user_id,
            "conversation_id": self.conversation_id,
            "conversation_history": self.conversation_history,
            "filters": self.filters,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Query":
        """Create from dictionary representation"""
        return cls(
            id=QueryId(value=data["id"]),
            text=data["text"],
            query_type=QueryType(data["query_type"]),
            status=QueryStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            metadata=data["metadata"],
            user_id=data.get("user_id"),
            conversation_id=data.get("conversation_id"),
            conversation_history=data.get("conversation_history", []),
            filters=data.get("filters", {}),
        )
