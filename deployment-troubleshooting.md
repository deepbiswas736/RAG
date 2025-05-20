# RAG Application Deployment Troubleshooting

## Current Status (May 11, 2025)

The RAG application consists of several microservices and infrastructure components. Currently, we're experiencing issues with some of the microservices not starting properly. This document tracks our troubleshooting steps and progress.

## Container Status

| Service | Status | Notes |
|---------|--------|-------|
| rag-zookeeper-1 | Running | Infrastructure service |
| rag-kafka-1 | Running | Infrastructure service |
| rag-mongodb-1 | Running (healthy) | Infrastructure service |
| rag-minio-1 | Running | Infrastructure service |
| rag-ollama-1 | Running | Infrastructure service |
| rag-kafka-ui-1 | Running | Monitoring service |
| rag-poppler-1 | Running (healthy) | Document processing dependency |
| rag-tesseract-1 | Running (healthy) | OCR service |
| rag-ui-1 | Running | Frontend UI |
| rag-document-processor-1 | Running (unhealthy) | Document processing service |
| rag-traefik-1 | Running (unhealthy) | API gateway |
| rag-document-service-1 | Exited (1) | Microservice - Failing |
| rag-llm-service-1 | Exited (1) | Microservice - Failing |
| rag-query-service-1 | Exited (1) | Microservice - Failing |
| rag-kafka_utility-1 | Exited (1) | Microservice - Failing |

## Current Problems

1. The following microservices are failing to start:
   - document-service
   - llm-service
   - query-service
   - kafka_utility

2. The document-processor and traefik services are running but in an unhealthy state.

## Troubleshooting Steps

### Step 1: Start Infrastructure Services First

We verified that the base infrastructure services (Zookeeper, Kafka, MongoDB, MinIO, Ollama) are running. These are prerequisites for the application services.

### Step 2: Attempt to Start Individual Services

We attempted to start each microservice individually using the `docker-compose up -d --no-deps [service]` command to avoid dependency cascades, but the services still failed.

## Action Plan

1. **Check Service Logs** - Examine the logs for each failing service to determine the root cause:
   ```bash
   docker logs rag-document-service-1
   docker logs rag-llm-service-1
   docker logs rag-query-service-1
   docker logs rag-kafka_utility-1
   ```

2. **Verify Configuration** - Review the environment variables and configuration for each service in the docker-compose.yml file:
   - Check if service URLs are correct
   - Verify authentication credentials
   - Ensure network connectivity between services

3. **Check for Port Conflicts** - Verify if there are port conflicts with other services:
   ```bash
   docker-compose ps
   netstat -ano | findstr PORT
   ```

4. **Check Volume Mounts** - Ensure that the volume mounts are correctly specified and accessible.

## Potential Solutions

1. **Fix Configuration** - Update environment variables to point to the correct services.
2. **Network Troubleshooting** - Ensure containers can communicate with each other.
3. **Service Dependencies** - Verify that dependent services are healthy before starting dependent services.

## Progress Tracking

| Date | Action | Result |
|------|--------|--------|
| May 11, 2025 | Started infrastructure services | Successful |
| May 11, 2025 | Attempted to start individual microservices | Failed - Exit code 1 |

## Next Steps

1. Check logs for specific error messages from failed services
2. Investigate network connectivity between containers
3. Check if there are missing env variables or configuration
4. Try running the services with debug logging enabled
