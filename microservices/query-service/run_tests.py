#!/usr/bin/env python
"""
Query Service Test Runner
------------------------
Helper script to run Query Service tests with proper configuration
"""

import os
import sys
import argparse
import subprocess


def main():
    parser = argparse.ArgumentParser(description="Run Query Service tests")
    parser.add_argument("--test-type", choices=["unit", "integration", "all"], default="all",
                      help="Type of tests to run (unit, integration, or all)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--docker", "-d", action="store_true", 
                      help="Start required Docker services for integration tests")
    parser.add_argument("--document-service-url", default="http://localhost:8000",
                      help="URL for Document Service")
    parser.add_argument("--llm-service-url", default="http://localhost:8001",
                      help="URL for LLM Service")
    parser.add_argument("--query-service-url", default="http://localhost:8002",
                      help="URL for Query Service")
    
    args = parser.parse_args()
    
    # Set environment variables
    os.environ["DOCUMENT_SERVICE_URL"] = args.document_service_url
    os.environ["LLM_SERVICE_URL"] = args.llm_service_url
    os.environ["QUERY_SERVICE_URL"] = args.query_service_url
    
    # Base directory for the project
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
    
    # Directory for tests
    test_dir = os.path.join(base_dir, "testing", "unit-integration-testing", "query-service")
    
    if args.docker and (args.test_type == "integration" or args.test_type == "all"):
        # Start Docker services if needed
        print("Starting Docker services for integration tests...")
        microservices_dir = os.path.join(base_dir, "microservices")
        
        # Command to start Docker services
        docker_cmd = [
            "docker-compose", 
            "-f", os.path.join(microservices_dir, "docker-compose.yml"),
            "up", "-d", 
            "document-service", "llm-service", "query-service", "mongodb"
        ]
        
        try:
            subprocess.run(docker_cmd, check=True)
            print("Docker services started successfully")
        except subprocess.CalledProcessError as e:
            print(f"Error starting Docker services: {e}")
            return 1
    
    # Determine which tests to run
    if args.test_type == "unit":
        test_path = os.path.join(test_dir, "unit")
    elif args.test_type == "integration":
        test_path = os.path.join(test_dir, "integration")
        os.environ["INTEGRATION_TESTS"] = "1"
    else:  # all
        test_path = test_dir
        os.environ["INTEGRATION_TESTS"] = "1"
    
    # Build pytest command
    pytest_cmd = ["pytest"]
    
    if args.verbose:
        pytest_cmd.append("-v")
    
    pytest_cmd.append(test_path)
    
    # Run the tests
    print(f"Running {args.test_type} tests...")
    try:
        result = subprocess.run(pytest_cmd, check=False)
        return result.returncode
    except Exception as e:
        print(f"Error running tests: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
