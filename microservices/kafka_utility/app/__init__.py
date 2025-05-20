"""Kafka Utility Service."""

# Import clients to make them available at the top level
from .clients import (
    DocumentServiceKafkaClient,
    QueryServiceKafkaClient,
    LLMServiceKafkaClient
)

# Import infrastructure adapters
from .infrastructure.adapters.kafka_producer import KafkaProducerAdapter
from .infrastructure.adapters.kafka_consumer import KafkaConsumerAdapter

# Import utilities
from .infrastructure.utils.message_serialization import MessageSerializer
from .infrastructure.utils.metrics import (
    track_producer_latency,
    track_consumer_latency,
    increment_message_produced,
    increment_message_consumed
)

# Import services
from .application.services.schema_registry_service import SchemaRegistryService
from .application.services.kafka_health_service import KafkaHealthService
from .application.services.topic_management_service import TopicManagementService

__version__ = "0.1.0"
