"""
Query Repository Interface
------------------------
Interface for query persistence operations
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime

from ..models.query import Query, QueryId, QueryStatus
from ..models.response import QueryResponse, ResponseId


class QueryRepository(ABC):
    """Repository interface for query operations"""
    
    @abstractmethod
    async def save(self, query: Query) -> None:
        """
        Save a query to the repository
        
        Args:
            query: Query to save
        """
        pass
    
    @abstractmethod
    async def find_by_id(self, query_id: QueryId) -> Optional[Query]:
        """
        Find a query by its ID
        
        Args:
            query_id: ID of the query to find
            
        Returns:
            Query if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def update(self, query: Query) -> None:
        """
        Update an existing query
        
        Args:
            query: Query to update
        """
        pass
    
    @abstractmethod
    async def find_by_conversation_id(self, conversation_id: str) -> List[Query]:
        """
        Find all queries in a conversation
        
        Args:
            conversation_id: ID of the conversation
            
        Returns:
            List of queries in the conversation
        """
        pass
    
    @abstractmethod
    async def find_by_user_id(self, user_id: str, limit: int = 100) -> List[Query]:
        """
        Find queries by user ID
        
        Args:
            user_id: User ID
            limit: Maximum number of queries to return
            
        Returns:
            List of queries by the user
        """
        pass
    
    @abstractmethod
    async def save_response(self, response: QueryResponse) -> None:
        """
        Save a query response
        
        Args:
            response: Response to save
        """
        pass
    
    @abstractmethod
    async def find_response_by_id(self, response_id: ResponseId) -> Optional[QueryResponse]:
        """
        Find a response by its ID
        
        Args:
            response_id: ID of the response to find
            
        Returns:
            Response if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def find_responses_by_query_id(self, query_id: QueryId) -> List[QueryResponse]:
        """
        Find all responses for a query
        
        Args:
            query_id: ID of the query
            
        Returns:
            List of responses for the query
        """
        pass
