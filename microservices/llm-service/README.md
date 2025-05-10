# LLM Service

A microservice for text generation and embedding creation using Ollama.

## Features

- Text generation with context support
- Streaming text generation
- Embedding creation for vector search
- Batch embedding processing
- Circuit breaker pattern for resilience
- Health monitoring

## API Endpoints

- `GET /health` - Check service health
- `POST /llm/generate` - Generate text
- `POST /llm/stream` - Stream text generation
- `POST /llm/embeddings` - Create embeddings
- `POST /llm/batch_embeddings` - Create batch embeddings

## Testing

The LLM Service includes a comprehensive test suite:

### Unit Tests

Located in `tests/unit/` directory:
- Domain model tests (`tests/unit/domain/models/`)
- Application service tests (`tests/unit/application/`)
- Infrastructure adapter tests (`tests/unit/infrastructure/`)
- API endpoint tests (`tests/unit/test_api.py`)

### Integration Tests

Located in `tests/integration/` directory:
- Tests that interact with a real Ollama service

### Running Tests

1. **Unit Tests Only:**
   ```powershell
   cd microservices/llm-service
   $env:PYTHONPATH = "."
   python -m pytest tests/unit -v
   ```

2. **With Integration Tests:**
   ```powershell
   cd microservices/llm-service
   $env:PYTHONPATH = "."
   $env:OLLAMA_INTEGRATION_TESTS = "true"
   $env:OLLAMA_BASE_URL = "http://localhost:11434"  # Optional: specify Ollama URL
   python -m pytest tests/unit tests/integration -v
   ```

3. **Using the test script:**
   ```powershell
   cd microservices/llm-service
   ./run_tests.ps1
   ```

## Development

### Environment Variables

- `OLLAMA_BASE_URL` - URL for Ollama API (default: "http://ollama:11434")
- `OLLAMA_DEFAULT_MODEL` - Default model for text generation (default: "llama2")
- `OLLAMA_EMBEDDING_MODEL` - Default model for embeddings (default: "nomic-embed-text")
- `OLLAMA_TIMEOUT` - Request timeout in seconds (default: 30.0)
- `LLM_CIRCUIT_FAILURE_THRESHOLD` - Failures before circuit opens (default: 5)
- `LLM_CIRCUIT_RESET_TIMEOUT` - Seconds before attempting reset (default: 300)
- `LLM_CIRCUIT_HALF_OPEN_TIMEOUT` - Half-open state timeout (default: 60)

### Docker Deployment

```bash
# Build the image
docker build -t llm-service:latest ./app

# Run the container
docker run -p 8001:8001 -e OLLAMA_BASE_URL=http://ollama:11434 llm-service:latest
```

### Docker Compose

The LLM Service can be deployed as part of the microservices architecture using Docker Compose:

```bash
cd microservices
docker-compose up -d ollama llm-service
```
