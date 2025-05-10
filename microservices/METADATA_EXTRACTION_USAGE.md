# Metadata Extraction in the RAG System

This document outlines how to use the metadata extraction functionality in the RAG microservices architecture.

## Overview

The metadata extraction process is an asynchronous workflow that involves multiple services:

1. **Document Service** - Initiates the metadata extraction request
2. **Kafka Utility Service** - Handles messaging between services
3. **LLM Service** - Processes metadata extraction requests and generates embeddings

## Sending Metadata Extraction Requests

The Document Service can send a request to extract metadata from a document using the Kafka Utility client:

```python
from kafka_utility.clients.document_service import DocumentServiceKafkaClient

async def request_metadata_extraction(document_id, document_path, file_type):
    # Initialize the client
    client = DocumentServiceKafkaClient()
    await client.initialize()
    
    # Send metadata extraction request
    success = await client.send_metadata_extraction_request(
        document_id=document_id,
        document_path=document_path,
        file_type=file_type,
        priority=5  # Optional priority (1-10)
    )
    
    if not success:
        # Handle sending failure
        print(f"Failed to send metadata extraction request for document {document_id}")
        
    # Close the client when done
    await client.close()
    
    return success
```

## Processing Flow

1. The Document Service uploads a document and sends a metadata extraction request.
2. The request is published to the `metadata_extraction` Kafka topic.
3. The LLM Service's metadata consumer receives the message and:
   - Extracts metadata from the document
   - Uses LLM to analyze and enhance the metadata
   - Creates embeddings for the metadata
   - Sends the results back to the Document Service

4. The Document Service receives the processed metadata and stores it with the document.

## Monitoring

The LLM Service provides an endpoint to monitor the status of metadata processing:

```
GET /metadata/status
```

Example response:
```json
{
  "running": true,
  "processed_count": 42,
  "failed_count": 3,
  "active_tasks": 2,
  "max_concurrent_tasks": 5,
  "topic": "metadata_extraction",
  "consumer_group_id": "llm_metadata_group"
}
```

## Integration in the Document Service

The Document Service should call the metadata extraction after processing a new document:

```python
# After document is uploaded and processed
document_id = "doc-123"
document_path = f"storage/documents/{document_id}.pdf"
file_type = "application/pdf"

# Request metadata extraction
await request_metadata_extraction(document_id, document_path, file_type)
```

## Error Handling

If metadata extraction fails, the LLM Service will send a failure notification back to the Document Service. 
The Document Service should handle these failures appropriately, such as by retrying or marking the document 
for manual review.

## Configuration Options

- `KAFKA_BOOTSTRAP_SERVERS` - Kafka bootstrap servers (default: "localhost:9092")
- `MAX_CONCURRENT_METADATA_TASKS` - Maximum number of concurrent metadata extraction tasks (default: 5)
