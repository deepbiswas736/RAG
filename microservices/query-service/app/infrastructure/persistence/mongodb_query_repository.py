"""
MongoDB Query Repository
---------------------
MongoDB implementation of the query repository
"""

import os
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from ...domain.interfaces.query_repository import QueryRepository
from ...domain.models.query import Query, QueryId, QueryStatus
from ...domain.models.response import QueryResponse, ResponseId

logger = logging.getLogger(__name__)


class MongoDBQueryRepository(QueryRepository):
    """MongoDB implementation of the query repository"""
    
    def __init__(self, connection_string: Optional[str] = None, database_name: Optional[str] = None):
        """
        Initialize the MongoDB query repository
        
        Args:
            connection_string: Optional MongoDB connection string (default: environment variable)
            database_name: Optional database name (default: environment variable)
        """
        self.connection_string = connection_string or os.environ.get("MONGODB_URL", "mongodb://localhost:27017")
        self.database_name = database_name or os.environ.get("MONGODB_DB_NAME", "query_db")
        
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None
        
        logger.info(f"Initialized MongoDB query repository for database: {self.database_name}")
    
    async def connect(self):
        """Connect to MongoDB"""
        if self.client is None:
            self.client = AsyncIOMotorClient(self.connection_string)
            self.db = self.client[self.database_name]
            logger.info(f"Connected to MongoDB database: {self.database_name}")
    
    async def disconnect(self):
        """Disconnect from MongoDB"""
        if self.client:
            self.client.close()
            self.client = None
            self.db = None
            logger.info("Disconnected from MongoDB")
    
    async def save(self, query: Query) -> None:
        """Save a query to the repository"""
        await self.connect()
        
        query_dict = query.to_dict()
        
        await self.db.queries.update_one(
            {"id": query_dict["id"]},
            {"$set": query_dict},
            upsert=True
        )
        
        logger.debug(f"Saved query with ID: {query.id.value}")
    
    async def find_by_id(self, query_id: QueryId) -> Optional[Query]:
        """Find a query by its ID"""
        await self.connect()
        
        query_dict = await self.db.queries.find_one({"id": query_id.value})
        
        if query_dict:
            logger.debug(f"Found query with ID: {query_id.value}")
            return Query.from_dict(query_dict)
        else:
            logger.debug(f"Query not found with ID: {query_id.value}")
            return None
    
    async def update(self, query: Query) -> None:
        """Update an existing query"""
        await self.connect()
        
        query_dict = query.to_dict()
        
        result = await self.db.queries.update_one(
            {"id": query_dict["id"]},
            {"$set": query_dict}
        )
        
        if result.modified_count == 0:
            logger.warning(f"Query update had no effect, ID: {query.id.value}")
        else:
            logger.debug(f"Updated query with ID: {query.id.value}")
    
    async def find_by_conversation_id(self, conversation_id: str) -> List[Query]:
        """Find all queries in a conversation"""
        await self.connect()
        
        cursor = self.db.queries.find({"conversation_id": conversation_id})
        query_dicts = await cursor.to_list(length=None)
        
        queries = [Query.from_dict(query_dict) for query_dict in query_dicts]
        logger.debug(f"Found {len(queries)} queries for conversation ID: {conversation_id}")
        
        return queries
    
    async def find_by_user_id(self, user_id: str, limit: int = 100) -> List[Query]:
        """Find queries by user ID"""
        await self.connect()
        
        cursor = self.db.queries.find({"user_id": user_id}).sort("created_at", -1).limit(limit)
        query_dicts = await cursor.to_list(length=None)
        
        queries = [Query.from_dict(query_dict) for query_dict in query_dicts]
        logger.debug(f"Found {len(queries)} queries for user ID: {user_id}")
        
        return queries
    
    async def save_response(self, response: QueryResponse) -> None:
        """Save a query response"""
        await self.connect()
        
        response_dict = response.to_dict()
        
        await self.db.responses.update_one(
            {"id": response_dict["id"]},
            {"$set": response_dict},
            upsert=True
        )
        
        logger.debug(f"Saved response with ID: {response.id.value}")
    
    async def find_response_by_id(self, response_id: ResponseId) -> Optional[QueryResponse]:
        """Find a response by its ID"""
        await self.connect()
        
        response_dict = await self.db.responses.find_one({"id": response_id.value})
        
        if response_dict:
            logger.debug(f"Found response with ID: {response_id.value}")
            return QueryResponse.from_dict(response_dict)
        else:
            logger.debug(f"Response not found with ID: {response_id.value}")
            return None
    
    async def find_responses_by_query_id(self, query_id: QueryId) -> List[QueryResponse]:
        """Find all responses for a query"""
        await self.connect()
        
        cursor = self.db.responses.find({"query_id": query_id.value})
        response_dicts = await cursor.to_list(length=None)
        
        responses = [QueryResponse.from_dict(response_dict) for response_dict in response_dicts]
        logger.debug(f"Found {len(responses)} responses for query ID: {query_id.value}")
        
        return responses
