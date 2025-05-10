# RAG Microservices Testing Strategy

This document outlines the comprehensive testing strategy for the RAG microservices architecture. Each microservice has dedicated tests organized in the centralized testing directory.

## Testing Structure

```
testing/
├── unit-integration-testing/     # Core unit and integration tests
│   ├── document-service/         # Document Service tests
│   │   ├── unit/                 # Unit tests for Document Service components
│   │   ├── integration/          # Integration tests for Document Service
│   │   └── conftest.py           # Shared fixtures for Document Service tests
│   │
│   ├── query-service/            # Query Service tests
│   │   ├── unit/                 # Unit tests for Query Service components
│   │   │   └── test_vector_search.py  # Tests for vector search functionality
│   │   ├── integration/          # Integration tests for Query Service
│   │   │   └── test_query_service_integration.py  # End-to-end tests
│   │   ├── conftest.py           # Shared fixtures for Query Service tests
│   │   ├── run_tests.py          # Test runner for Query Service tests
│   │   └── README.md             # Documentation for Query Service tests
│   │
│   └── llm-service/              # LLM Service tests (to be implemented)
│
├── performance-testing/          # Performance and load testing scripts
├── mobile-app-testing/           # Mobile client application tests
└── web-application-testing/      # Web client application tests
```

## Testing Approach

### Unit Testing

Each microservice has dedicated unit tests covering:
- Domain entities and value objects
- Service implementations
- Infrastructure components
- Adapters and interfaces
- Utility classes

Unit tests are designed to be fast and isolated, with dependencies properly mocked.

### Integration Testing

Integration tests validate interactions between components:
- API endpoint testing
- Database interaction testing
- Service-to-service communication testing
- Message bus integration testing

Integration tests run against containerized dependencies when necessary.

### End-to-End Testing

End-to-end tests validate complete user flows across the entire system:
- Document upload, processing, and retrieval
- Query processing and response generation
- Authentication and authorization
- Error handling and recovery

## Running Tests

### Using Dedicated Test Runners

Each microservice has a dedicated test runner script (`run_tests.py`) that:
- Configures the test environment
- Starts necessary dependencies (optional)
- Runs the appropriate tests
- Reports results

Example for Query Service:

```bash
cd e:\code\experimental\RAG\testing\unit-integration-testing\query-service
python run_tests.py --test-type unit --verbose
```

### Using pytest Directly

Tests can also be run directly with pytest:

```bash
cd e:\code\experimental\RAG
pytest testing/unit-integration-testing/query-service/unit -v
```

## Test Coverage Areas

### Vector Search Testing

The Query Service includes comprehensive tests for vector search functionality:

1. **Ranking Methods**:
   - Testing hybrid ranking (vector + keyword + position + metadata)
   - Testing keyword-focused ranking
   - Testing metadata-focused ranking

2. **Query Analysis**:
   - Testing automatic ranking method selection based on query type
   - Testing query term extraction and processing
   - Testing metadata relevance calculation

3. **Integration with Services**:
   - Testing embedding generation via LLM Service
   - Testing document retrieval via Document Service
   - Testing end-to-end query processing workflows

## Adding New Tests

When adding new tests:

1. Place them in the appropriate directory based on test type (unit/integration)
2. Leverage shared fixtures from conftest.py
3. Follow the naming convention: `test_*.py` for files and `test_*` for functions
4. Add documentation to the relevant README.md file
5. Ensure test isolation (no dependencies between tests)

## Test Environment Configuration

Tests can be configured through environment variables:
- `DOCUMENT_SERVICE_URL`: URL for Document Service
- `LLM_SERVICE_URL`: URL for LLM Service
- `QUERY_SERVICE_URL`: URL for Query Service
- `MONGODB_URL`: URL for MongoDB
- `INTEGRATION_TESTS`: Set to "1" to run integration tests
- Various configuration options specific to each service

## Continuous Integration

For CI/CD pipelines, use the test runners with appropriate flags:

```bash
# Run all tests with Docker dependencies
python testing/unit-integration-testing/query-service/run_tests.py --docker --verbose

# Run only unit tests for faster CI builds
python testing/unit-integration-testing/query-service/run_tests.py --test-type unit --verbose
```
