# Query Service Tests

The tests for this microservice have been moved to the centralized testing directory:

```
e:\code\experimental\RAG\testing\unit-integration-testing\query-service\
```

To run tests, navigate to that directory and use the `run_tests.py` script:

```bash
cd e:\code\experimental\RAG\testing\unit-integration-testing\query-service\
python run_tests.py --verbose
```

Or run specific test types:

```bash
# Run only unit tests
python run_tests.py --test-type unit --verbose

# Run only integration tests with automatic Docker container startup
python run_tests.py --test-type integration --docker --verbose
```

See the README.md in that directory for more details on testing options.
