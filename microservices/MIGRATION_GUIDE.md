# Switching from Monolithic to Microservices Implementation

This document outlines the steps to switch from the monolithic implementation to the new microservices architecture with metadata extraction.

## 1. Prerequisites

Before making the switch, ensure:

- All microservices are properly implemented 
- The metadata extraction functionality is tested
- Database migrations are prepared if necessary
- Backup of current data is available

## 2. Switch Implementation

### Step 1: Stop the current services

```bash
cd e:\code\experimental\RAG
docker-compose down
```

### Step 2: Copy the new configuration files

```bash
# Backup original files
copy docker-compose.yml docker-compose.yml.bak
copy .\traefik\dynamic_conf.yml .\traefik\dynamic_conf.yml.bak

# Replace with new files
copy docker-compose-new.yml docker-compose.yml
copy .\traefik\dynamic_conf_new.yml .\traefik\dynamic_conf.yml
```

### Step 3: Start the new microservices

```bash
docker-compose up -d
```

### Step 4: Monitor the services

Check that all services are starting correctly:

```bash
docker-compose ps
```

Monitor the logs for any issues:

```bash
docker-compose logs -f
```

## 3. Testing

After switching to the new implementation, test each of the following flows:

1. **Document Upload**
   - Upload a document to the document service
   - Verify that metadata extraction is triggered
   - Check the metadata extraction status

2. **Metadata Extraction Process**
   - Monitor Kafka topics to ensure messages are flowing correctly
   - Check LLM Service logs for processing status
   - Verify that extracted metadata is stored correctly

3. **Query Processing**
   - Submit a query to the query service
   - Verify that results include metadata

## 4. Rollback Plan

If issues are encountered, follow these steps to roll back to the original implementation:

```bash
# Stop the new services
docker-compose down

# Restore the original configuration
copy docker-compose.yml.bak docker-compose.yml
copy .\traefik\dynamic_conf.yml.bak .\traefik\dynamic_conf.yml

# Start the original services
docker-compose up -d
```

## 5. Post-Migration Tasks

After a successful migration:

- Update documentation to reflect the new architecture
- Configure monitoring and alerts for the new services
- Update CI/CD pipelines if necessary
- Review and adjust resource allocations based on performance
