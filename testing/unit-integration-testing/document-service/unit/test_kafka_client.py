"""
Unit tests for Kafka Client
"""

import pytest
import sys
import os
from unittest.mock import patch, MagicMock, AsyncMock

# Add the microservices directory to the Python path
sys.path.append(os.path.abspath("microservices/document-service/app"))

from infrastructure.messaging.kafka_client import KafkaClient


class TestKafkaClient:
    """Tests for KafkaClient"""
    
    @pytest.fixture
    def mock_kafka_producer(self):
        """Fixture for mocking Kafka producer"""
        with patch("aiokafka.AIOKafkaProducer") as mock_producer_class:
            mock_producer = AsyncMock()
            mock_producer_class.return_value = mock_producer
            
            # Mock methods
            mock_producer.start = AsyncMock()
            mock_producer.send_and_wait = AsyncMock()
            mock_producer.stop = AsyncMock()
            
            yield mock_producer
    
    @pytest.fixture
    def kafka_client(self, mock_kafka_producer):
        """Fixture for creating a Kafka client with mocked producer"""
        return KafkaClient(
            bootstrap_servers="localhost:9092",
            client_id="test-client"
        )
    
    @pytest.mark.asyncio
    async def test_init(self, kafka_client):
        """Test initialization"""
        # Check that the client was initialized with the correct topics
        assert kafka_client.document_created_topic == "document-created"
        assert kafka_client.document_processed_topic == "document-processed"
        assert kafka_client.document_chunked_topic == "document-chunked"
        assert kafka_client.document_deleted_topic == "document-deleted"
        
    @pytest.mark.asyncio
    async def test_start(self, kafka_client, mock_kafka_producer):
        """Test starting the client"""
        # Start the client
        await kafka_client.start()
        
        # Check that producer was started
        mock_kafka_producer.start.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_stop(self, kafka_client, mock_kafka_producer):
        """Test stopping the client"""
        # Stop the client
        await kafka_client.stop()
        
        # Check that producer was stopped
        mock_kafka_producer.stop.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_send_document_created_event(self, kafka_client, mock_kafka_producer):
        """Test sending document created event"""
        # Test data
        document_id = "12345"
        document_data = {
            "id": document_id,
            "name": "test.pdf",
            "file_type": "pdf"
        }
        
        # Send event
        await kafka_client.send_document_created_event(document_id, document_data)
        
        # Check that the producer was called
        mock_kafka_producer.send_and_wait.assert_called_once()
        
        call_args = mock_kafka_producer.send_and_wait.call_args
        assert call_args[0][0] == "document-created"  # topic
        
        # Check the message value
        message_value = call_args[0][1]
        import json
        message_dict = json.loads(message_value)
        
        assert message_dict["event_type"] == "document_created"
        assert message_dict["document_id"] == document_id
        assert message_dict["data"]["id"] == document_id
        assert message_dict["data"]["name"] == "test.pdf"
        
    @pytest.mark.asyncio
    async def test_send_document_processed_event(self, kafka_client, mock_kafka_producer):
        """Test sending document processed event"""
        # Test data
        document_id = "12345"
        processing_status = "completed"
        metadata = {"page_count": 10}
        
        # Send event
        await kafka_client.send_document_processed_event(document_id, processing_status, metadata)
        
        # Check that the producer was called
        mock_kafka_producer.send_and_wait.assert_called_once()
        
        call_args = mock_kafka_producer.send_and_wait.call_args
        assert call_args[0][0] == "document-processed"  # topic
        
        # Check the message value
        message_value = call_args[0][1]
        import json
        message_dict = json.loads(message_value)
        
        assert message_dict["event_type"] == "document_processed"
        assert message_dict["document_id"] == document_id
        assert message_dict["data"]["status"] == processing_status
        assert message_dict["data"]["metadata"]["page_count"] == 10
        
    @pytest.mark.asyncio
    async def test_send_document_chunked_event(self, kafka_client, mock_kafka_producer):
        """Test sending document chunked event"""
        # Test data
        document_id = "12345"
        chunk_count = 5
        
        # Send event
        await kafka_client.send_document_chunked_event(document_id, chunk_count)
        
        # Check that the producer was called
        mock_kafka_producer.send_and_wait.assert_called_once()
        
        call_args = mock_kafka_producer.send_and_wait.call_args
        assert call_args[0][0] == "document-chunked"  # topic
        
        # Check the message value
        message_value = call_args[0][1]
        import json
        message_dict = json.loads(message_value)
        
        assert message_dict["event_type"] == "document_chunked"
        assert message_dict["document_id"] == document_id
        assert message_dict["data"]["chunk_count"] == chunk_count
        
    @pytest.mark.asyncio
    async def test_send_document_deleted_event(self, kafka_client, mock_kafka_producer):
        """Test sending document deleted event"""
        # Test data
        document_id = "12345"
        
        # Send event
        await kafka_client.send_document_deleted_event(document_id)
        
        # Check that the producer was called
        mock_kafka_producer.send_and_wait.assert_called_once()
        
        call_args = mock_kafka_producer.send_and_wait.call_args
        assert call_args[0][0] == "document-deleted"  # topic
        
        # Check the message value
        message_value = call_args[0][1]
        import json
        message_dict = json.loads(message_value)
        
        assert message_dict["event_type"] == "document_deleted"
        assert message_dict["document_id"] == document_id
        
    @pytest.mark.asyncio
    async def test_send_message(self, kafka_client, mock_kafka_producer):
        """Test sending a custom message"""
        # Test data
        topic = "custom-topic"
        key = "test-key"
        message = {"type": "custom", "data": "test-data"}
        
        # Send message
        await kafka_client._send_message(topic, key, message)
        
        # Check that the producer was called
        mock_kafka_producer.send_and_wait.assert_called_once()
        
        call_args = mock_kafka_producer.send_and_wait.call_args
        assert call_args[0][0] == topic
        
        # Check the message value and key
        assert call_args[1]["key"] == key.encode() if key else None
