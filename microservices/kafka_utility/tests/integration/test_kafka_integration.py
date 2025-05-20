"""
Integration Test for Kafka Utility Service

This test verifies that the Kafka Utility Service can successfully connect to Kafka,
create topics, produce messages, and consume messages.

Note: This test requires a running Kafka instance.
"""

import os
import sys
import unittest
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

# Add parent directory to path for imports
parent_dir = Path(__file__).parent.parent.parent
sys.path.append(str(parent_dir))

from app.infrastructure.adapters.kafka_producer import KafkaProducerAdapter
from app.infrastructure.adapters.kafka_consumer import KafkaConsumerAdapter
from app.application.services.topic_management_service import TopicManagementService
from app.application.services.kafka_health_service import KafkaHealthService
from app.application.services.schema_registry_service import SchemaRegistryService
from app.infrastructure.utils.message_serialization import MessageSerializer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TEST_TOPIC = "kafka_utility_test"

class KafkaUtilityIntegrationTest(unittest.IsolatedAsyncioTestCase):
    """Integration tests for Kafka Utility Service components."""
    
    async def asyncSetUp(self):
        """Set up the test environment."""
        # Check if Kafka is available
        self.health_service = KafkaHealthService(bootstrap_servers=BOOTSTRAP_SERVERS)
        kafka_available = await self.health_service.check_kafka_availability()
        if not kafka_available:
            self.skipTest("Kafka is not available at " + BOOTSTRAP_SERVERS)
        
        # Create test topic
        self.topic_service = TopicManagementService(bootstrap_servers=BOOTSTRAP_SERVERS)
        topic_created = await self.topic_service.ensure_topic_exists(
            topic_name=TEST_TOPIC,
            partitions=1,
            replication_factor=1
        )
        if not topic_created:
            self.skipTest("Failed to create test topic")
        
        # Initialize producer and consumer
        self.producer = KafkaProducerAdapter(bootstrap_servers=BOOTSTRAP_SERVERS)
        
        # Initialize schema registry and serializer
        self.schema_registry = SchemaRegistryService()
        await self.schema_registry.initialize()
        self.message_serializer = MessageSerializer(schema_registry=self.schema_registry)
        
        # Create a queue for received messages
        self.message_queue = asyncio.Queue()
    
    async def asyncTearDown(self):
        """Clean up after tests."""
        # Delete test topic
        if hasattr(self, 'topic_service'):
            await self.topic_service.delete_topic(TEST_TOPIC)
        
        # Close producer
        if hasattr(self, 'producer'):
            await self.producer.close()
        
        # Close health service
        if hasattr(self, 'health_service'):
            await self.health_service.close()
        
        # Close topic service
        if hasattr(self, 'topic_service'):
            await self.topic_service.close()
    
    @asynccontextmanager
    async def consumer(self, group_id="test-group"):
        """Create and manage a consumer with a context manager."""
        consumer = KafkaConsumerAdapter(
            bootstrap_servers=BOOTSTRAP_SERVERS,
            group_id=group_id
        )
        
        # Register handler for test topic
        consumer.register_handler(TEST_TOPIC, self.message_handler)
        
        try:
            # Start consumer
            await consumer.start_consuming()
            yield consumer
        finally:
            # Stop consumer
            await consumer.stop()
    
    async def message_handler(self, message):
        """Handle received messages by adding them to the queue."""
        await self.message_queue.put(message)
    
    async def test_produce_consume(self):
        """Test producing and consuming messages."""
        # Create a test message
        test_message = {
            "id": "test123",
            "value": "Hello, Kafka!",
            "timestamp": 1620000000000
        }
        
        # Create an envelope
        envelope = self.message_serializer.create_envelope(
            payload=test_message,
            message_type="test.message"
        )
        
        # Start consumer in a context manager
        async with self.consumer():
            # Produce a message
            success = await self.producer.send_message(
                topic=TEST_TOPIC,
                key="test-key",
                value=envelope
            )
            self.assertTrue(success, "Failed to send message")
            
            # Wait for the message to be consumed (with timeout)
            try:
                received_message = await asyncio.wait_for(self.message_queue.get(), timeout=10)
                
                # Verify the message
                self.assertEqual(received_message["payload"]["id"], test_message["id"])
                self.assertEqual(received_message["payload"]["value"], test_message["value"])
                self.assertEqual(received_message["metadata"]["messageType"], "test.message")
            except asyncio.TimeoutError:
                self.fail("Timed out waiting for message")


if __name__ == "__main__":
    unittest.main()
