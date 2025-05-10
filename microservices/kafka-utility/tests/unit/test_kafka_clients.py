"""
Tests for the Kafka client libraries.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from app.clients.document_service import DocumentServiceKafkaClient
from app.clients.query_service import QueryServiceKafkaClient
from app.clients.llm_service import LLMServiceKafkaClient


@pytest.fixture
def mock_producer():
    """Create a mock Kafka producer."""
    producer = MagicMock()
    producer.send_message = AsyncMock(return_value=True)
    producer.close = AsyncMock()
    return producer


@pytest.fixture
def mock_schema_registry():
    """Create a mock schema registry."""
    registry = MagicMock()
    registry.initialize = AsyncMock()
    return registry


@pytest.fixture
def mock_serializer():
    """Create a mock message serializer."""
    serializer = MagicMock()
    serializer.create_envelope = MagicMock(return_value={"metadata": {}, "payload": {}})
    serializer.validate_message = MagicMock(return_value=True)
    return serializer


@pytest.mark.asyncio
async def test_document_service_client(mock_producer, mock_schema_registry, mock_serializer):
    """Test DocumentServiceKafkaClient."""
    with patch("app.clients.document_service.document_service_client.KafkaProducerAdapter", 
               return_value=mock_producer), \
         patch("app.clients.document_service.document_service_client.SchemaRegistryService", 
               return_value=mock_schema_registry), \
         patch("app.clients.document_service.document_service_client.MessageSerializer", 
               return_value=mock_serializer):
        
        client = DocumentServiceKafkaClient(bootstrap_servers="test:9092")
        
        # Test initialization
        await client.initialize()
        mock_schema_registry.initialize.assert_awaited_once()
        
        # Test sending document created event
        result = await client.send_document_created_event(
            document_id="doc123",
            file_name="test.pdf",
            file_type="pdf",
            file_size=1024,
            user_id="user456",
            metadata={"category": "test"}
        )
        
        assert result is True
        mock_serializer.create_envelope.assert_called_once()
        mock_serializer.validate_message.assert_called_once_with(
            mock_serializer.create_envelope.return_value, "document_event")
        mock_producer.send_message.assert_awaited_once_with(
            topic="document_events", key="doc123", value=mock_serializer.create_envelope.return_value)
        
        # Test close
        await client.close()
        mock_producer.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_query_service_client(mock_producer, mock_schema_registry, mock_serializer):
    """Test QueryServiceKafkaClient."""
    with patch("app.clients.query_service.query_service_client.KafkaProducerAdapter", 
               return_value=mock_producer), \
         patch("app.clients.query_service.query_service_client.SchemaRegistryService", 
               return_value=mock_schema_registry), \
         patch("app.clients.query_service.query_service_client.MessageSerializer", 
               return_value=mock_serializer):
        
        client = QueryServiceKafkaClient(bootstrap_servers="test:9092")
        
        # Test initialization
        await client.initialize()
        mock_schema_registry.initialize.assert_awaited_once()
        
        # Test sending query event
        result = await client.send_query_event(
            query_id="query123",
            query="What is RAG?",
            user_id="user456",
            filters={"documentType": "pdf"}
        )
        
        assert result is True
        mock_serializer.create_envelope.assert_called_once()
        mock_serializer.validate_message.assert_called_once_with(
            mock_serializer.create_envelope.return_value, "query_event")
        mock_producer.send_message.assert_awaited_once_with(
            topic="query_events", key="query123", value=mock_serializer.create_envelope.return_value)


@pytest.mark.asyncio
async def test_llm_service_client(mock_producer, mock_schema_registry, mock_serializer):
    """Test LLMServiceKafkaClient."""
    with patch("app.clients.llm_service.llm_service_client.KafkaProducerAdapter", 
               return_value=mock_producer), \
         patch("app.clients.llm_service.llm_service_client.SchemaRegistryService", 
               return_value=mock_schema_registry), \
         patch("app.clients.llm_service.llm_service_client.MessageSerializer", 
               return_value=mock_serializer):
        
        client = LLMServiceKafkaClient(bootstrap_servers="test:9092")
        
        # Test initialization
        await client.initialize()
        mock_schema_registry.initialize.assert_awaited_once()
        
        # Test sending embedding request
        result = await client.send_embedding_request(
            task_id="task123",
            input_text="Embed this text",
            model="text-embedding-3-small",
            priority=8
        )
        
        assert result is True
        mock_serializer.create_envelope.assert_called_once()
        mock_serializer.validate_message.assert_called_once_with(
            mock_serializer.create_envelope.return_value, "llm_task")
        mock_producer.send_message.assert_awaited_once_with(
            topic="llm_tasks", key="task123", value=mock_serializer.create_envelope.return_value)
