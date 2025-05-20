# Kafka Utility Service Configuration

This document provides examples of how to integrate the Kafka Utility Service into the other microservices.

## Installation

To use the Kafka Utility client libraries in your microservice, add the following to your `requirements.txt`:

```
kafka_utility @ git+https://github.com/your-org/rag-application.git#subdirectory=microservices/kafka_utility
```

## Document Service Integration

### Producer Example
```python
from kafka_utility.clients.document_service import DocumentServiceKafkaClient

async def notify_document_processed(document_id, status, metadata):
    # Initialize the client
    client = DocumentServiceKafkaClient()
    await client.initialize()
    
    # Send document processed event
    success = await client.send_document_processed_event(
        document_id=document_id,
        status=status,
        metadata=metadata
    )
    
    if not success:
        # Handle sending failure
        pass
        
    # Close the client when done
    await client.close()
```

### Consumer Example
```python
import asyncio
from kafka_utility.infrastructure.adapters.kafka_consumer import KafkaConsumerAdapter

async def handle_document_event(message):
    document_id = message["payload"]["documentId"]
    status = message["payload"]["status"]
    
    # Process the document event
    print(f"Processing document {document_id} with status {status}")

async def start_document_consumer():
    # Initialize consumer
    consumer = KafkaConsumerAdapter(
        bootstrap_servers="kafka:9092",
        group_id="document-service-group",
        auto_offset_reset="earliest"
    )
    
    # Register handler for document events
    consumer.register_handler("document_events", handle_document_event)
    
    # Start consuming
    await consumer.start_consuming()
```

## Query Service Integration

### Producer Example
```python
from kafka_utility.clients.query_service import QueryServiceKafkaClient
import uuid

async def submit_query(query_text, user_id=None, filters=None):
    # Generate a new query ID
    query_id = str(uuid.uuid4())
    
    # Initialize the client
    client = QueryServiceKafkaClient()
    await client.initialize()
    
    # Send query event
    success = await client.send_query_event(
        query_id=query_id,
        query=query_text,
        user_id=user_id,
        filters=filters
    )
    
    if success:
        return query_id
    else:
        return None
```

### Consumer Example
```python
import asyncio
from kafka_utility.infrastructure.adapters.kafka_consumer import KafkaConsumerAdapter

async def handle_query_event(message):
    query_id = message["payload"]["queryId"]
    query = message["payload"]["query"]
    user_id = message["payload"].get("userId")
    
    # Process the query
    print(f"Processing query {query_id} from user {user_id}: {query}")
    
    # Process the query and generate response
    # ...

async def start_query_consumer():
    # Initialize consumer
    consumer = KafkaConsumerAdapter(
        bootstrap_servers="kafka:9092",
        group_id="query-service-group",
        auto_offset_reset="earliest"
    )
    
    # Register handler for query events
    consumer.register_handler("query_events", handle_query_event)
    
    # Start consuming
    await consumer.start_consuming()
```

## LLM Service Integration

### Producer Example
```python
from kafka_utility.clients.llm_service import LLMServiceKafkaClient
import uuid
import time

async def request_embedding(text, model="default"):
    # Generate a new task ID
    task_id = str(uuid.uuid4())
    
    # Initialize the client
    client = LLMServiceKafkaClient()
    await client.initialize()
    
    # Send embedding request
    start_time = time.time()
    success = await client.send_embedding_request(
        task_id=task_id,
        input_text=text,
        model=model
    )
    
    if success:
        return task_id
    else:
        return None
```

### Consumer Example
```python
import asyncio
from kafka_utility.infrastructure.adapters.kafka_consumer import KafkaConsumerAdapter

async def handle_llm_task(message):
    task_id = message["payload"]["taskId"]
    task_type = message["payload"]["taskType"]
    
    if task_type == "embedding":
        input_text = message["payload"]["input"]
        # Process embedding request
        # ...
    elif task_type == "completion":
        # Process completion request
        # ...
    
async def start_llm_consumer():
    # Initialize consumer
    consumer = KafkaConsumerAdapter(
        bootstrap_servers="kafka:9092",
        group_id="llm-service-group",
        auto_offset_reset="earliest"
    )
    
    # Register handler for LLM tasks
    consumer.register_handler("llm_tasks", handle_llm_task)
    
    # Start consuming
    await consumer.start_consuming()
```
