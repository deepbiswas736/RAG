# Kafka Utility Service

This service provides standardized Kafka messaging patterns and client libraries for the RAG microservices architecture. It centralizes Kafka messaging functionality, ensuring consistent message formats, error handling, and observability across all microservices.

## Features

- Standardized message schemas using JSON Schema
- Client libraries for all microservices (Document Service, Query Service, LLM Service)
- Resilient producer and consumer abstractions with automatic retries
- Connection pooling and automatic reconnection
- Observability and monitoring via Prometheus metrics
- Message validation and versioning
- Circuit breaker pattern for enhanced resilience
- Request-reply pattern support for synchronous-style communication

## Directory Structure

```
app/
├── application/
│   └── services/           # Core service implementations
├── clients/                # Client libraries for other services
│   ├── document-service/   # Document Service client
│   ├── llm-service/        # LLM Service client
│   └── query-service/      # Query Service client
├── domain/
│   ├── entities/           # Domain entities
│   ├── interfaces/         # Service interfaces
│   └── schemas/            # JSON message schemas
└── infrastructure/
    ├── adapters/           # Adapters for Kafka implementation
    └── utils/              # Utility functions
```

## Getting Started

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure Kafka connection settings in `.env` file:
```
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
KAFKA_SECURITY_PROTOCOL=PLAINTEXT
```

3. Import the appropriate client in your microservice:
```python
from kafka_utility.clients.document_service import DocumentServiceKafkaClient

kafka_client = DocumentServiceKafkaClient()
```

## Message Schemas

All message schemas are defined using JSON Schema and are located in the `domain/schemas` directory. These schemas enforce a consistent message format across all services.

## Client Usage Examples

### Document Service

```python
from kafka_utility.clients.document_service import DocumentServiceKafkaClient

# Initialize client
client = DocumentServiceKafkaClient()

# Send document processed event
await client.send_document_processed_event(
    document_id="doc123",
    status="success",
    metadata={"title": "Example Document"}
)
```

### Query Service

```python
from kafka_utility.clients.query_service import QueryServiceKafkaClient

# Initialize client
client = QueryServiceKafkaClient()

# Send query event
await client.send_query_event(
    query_id="query123",
    query="What is machine learning?",
    user_id="user456"
)
```

## Testing

Run unit tests:
```bash
pytest tests/unit
```

Run integration tests:
```bash
pytest tests/integration
```
