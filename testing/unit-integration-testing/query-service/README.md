# Query Service Testing

This directory contains unit and integration tests for the Query Service microservice, with a focus on the vector search capabilities and client-side ranking functionality.

## Directory Structure

```
query-service/
├── conftest.py            # Shared fixtures for all tests
├── run_tests.py           # Test runner script
├── integration/           # Integration tests
│   └── test_query_service_integration.py
└── unit/                 # Unit tests
    └── test_vector_search.py
```

## Test Categories

### Unit Tests

Unit tests are focused on testing individual components of the Query Service:

- Vector search with client-side ranking
- Metadata embedding generation and scoring
- Ranking methods and algorithms
- Query classification

### Integration Tests

Integration tests validate the end-to-end functionality of the Query Service with other microservices:

- Complete query processing flow
- Vector search with metadata integration
- Different ranking methods comparison

## Running the Tests

### Using the Test Runner

The easiest way to run tests is using the provided `run_tests.py` script:

```bash
cd e:\code\experimental\RAG\testing\unit-integration-testing\query-service
python run_tests.py --test-type unit --verbose
```

The script supports the following options:
- `--test-type`: Choose between 'unit', 'integration', or 'all' (default: all)
- `--verbose` or `-v`: Enable verbose output
- `--docker` or `-d`: Automatically start required Docker services for integration tests
- `--document-service-url`: URL for Document Service (default: http://localhost:8000)
- `--llm-service-url`: URL for LLM Service (default: http://localhost:8001)
- `--query-service-url`: URL for Query Service (default: http://localhost:8002)

### Running Tests Manually

#### Running Unit Tests

```bash
cd e:\code\experimental\RAG
pytest testing/unit-integration-testing/query-service/unit -v
```

#### Running Integration Tests

To run integration tests, you need to have the Document Service, LLM Service, and Query Service running. You can use Docker Compose to start these services:

```bash
cd e:\code\experimental\RAG\microservices
docker-compose up -d document-service llm-service query-service mongodb
```

Then run the integration tests with:

```bash
cd e:\code\experimental\RAG
set INTEGRATION_TESTS=1
pytest testing/unit-integration-testing/query-service/integration -v
```

#### Running All Tests

```bash
cd e:\code\experimental\RAG
pytest testing/unit-integration-testing/query-service -v
```

## Test Parameters

The test environment is configured with the following default parameters:

- Document Service URL: `http://localhost:8000`
- LLM Service URL: `http://localhost:8001`
- Query Service URL: `http://localhost:8002`
- MongoDB URL: `mongodb://user:password@localhost:27017`
- Metadata Search: Enabled

These parameters can be overridden by setting environment variables before running the tests.

## Adding New Tests

When adding new tests:

1. Place unit tests in the `unit/` directory
2. Place integration tests in the `integration/` directory
3. Add shared fixtures to `conftest.py`
4. Update this README as needed
