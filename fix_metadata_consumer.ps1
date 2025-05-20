# Fix Metadata Consumer PowerShell Script
# This script helps diagnose and fix issues with the metadata extraction consumer

Write-Host "Metadata Extraction Consumer Diagnostic and Repair Script" -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is running and containers are up
$dockerStatus = docker ps --format "{{.Names}}" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker doesn't seem to be running. Please start Docker first." -ForegroundColor Red
    exit 1
}

# Check if the RAG system containers are running
Write-Host "Checking RAG system containers..." -ForegroundColor Yellow
$ragContainers = $dockerStatus | Where-Object { $_ -like "rag_*" }
if (-not $ragContainers) {
    Write-Host "No RAG containers found running. Starting the system..." -ForegroundColor Yellow
    Set-Location e:\code\experimental\RAG
    docker-compose up -d
    Write-Host "Waiting 30 seconds for services to initialize..." -ForegroundColor Yellow
    Start-Sleep -Seconds 30
}
else {
    Write-Host "RAG containers are running:" -ForegroundColor Green
    $ragContainers | ForEach-Object { Write-Host "- $_" }
}

# Check Kafka topics
Write-Host "`nChecking Kafka topics..." -ForegroundColor Yellow
$kafkaTopics = docker exec rag_kafka kafka-topics --list --bootstrap-server kafka:29092 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to list Kafka topics. Kafka container might not be healthy." -ForegroundColor Red
}
else {
    Write-Host "Available Kafka topics:" -ForegroundColor Green
    $kafkaTopics | ForEach-Object { Write-Host "- $_" }
    
    # Check for metadata_extraction topic
    if ($kafkaTopics -contains "metadata_extraction" -or $kafkaTopics -contains "metadata-extraction") {
        Write-Host "Metadata extraction topic exists!" -ForegroundColor Green
    }
    else {
        Write-Host "Metadata extraction topic does not exist. Creating..." -ForegroundColor Yellow
        docker exec rag_kafka kafka-topics --create --topic metadata_extraction --bootstrap-server kafka:29092 --partitions 1 --replication-factor 1
    }
}

# Check consumer groups
Write-Host "`nChecking Kafka consumer groups..." -ForegroundColor Yellow
$consumerGroups = docker exec rag_kafka kafka-consumer-groups --list --bootstrap-server kafka:29092 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to list consumer groups." -ForegroundColor Red
}
else {
    Write-Host "Consumer groups:" -ForegroundColor Green
    $consumerGroups | ForEach-Object { Write-Host "- $_" }
}

# Check LLM service
Write-Host "`nChecking LLM service health..." -ForegroundColor Yellow
try {
    $healthResponse = Invoke-RestMethod -Uri "http://localhost/api/llm/health" -Method Get -ErrorAction Stop
    Write-Host "LLM service health status: $($healthResponse.status)" -ForegroundColor Green
    
    # Check metadata consumer status
    Write-Host "`nChecking metadata consumer status..." -ForegroundColor Yellow
    try {
        $metadataStatus = Invoke-RestMethod -Uri "http://localhost/api/llm/metadata/status" -Method Get -ErrorAction Stop
        Write-Host "Metadata consumer topic: $($metadataStatus.topic)" -ForegroundColor Green
        Write-Host "Consumer group ID: $($metadataStatus.consumer_group_id)" -ForegroundColor Green
        Write-Host "Processed count: $($metadataStatus.processed_count)" -ForegroundColor Green
        Write-Host "Failed count: $($metadataStatus.failed_count)" -ForegroundColor Green
    }
    catch {
        Write-Host "Failed to check metadata consumer status: $_" -ForegroundColor Red
    }
    
    # Get detailed diagnostics
    Write-Host "`nGetting detailed metadata consumer diagnostics..." -ForegroundColor Yellow
    try {
        $diagnostics = Invoke-RestMethod -Uri "http://localhost/api/llm/metadata/diagnostics" -Method Get -ErrorAction Stop
        Write-Host "Consumer running: $($diagnostics.consumer_status.running)" -ForegroundColor $(if ($diagnostics.consumer_status.running) { "Green" } else { "Red" })
        
        if ($diagnostics.kafka_health -and $diagnostics.kafka_health.connected) {
            Write-Host "Kafka connection: Successful" -ForegroundColor Green
        }
        else {
            Write-Host "Kafka connection issues detected" -ForegroundColor Red
        }
        
        # Check if consumer needs to be fixed
        $needsFixing = -not $diagnostics.consumer_status.running -or
                       -not $diagnostics.kafka_health.connected -or
                       -not $consumerGroups -contains $metadataStatus.consumer_group_id
        
        if ($needsFixing) {
            Write-Host "`nIssues detected with metadata consumer. Attempting to fix..." -ForegroundColor Yellow
            try {
                $fixResponse = Invoke-RestMethod -Uri "http://localhost/api/llm/metadata/fix" -Method Post -ErrorAction Stop
                Write-Host "Fix attempted with results:" -ForegroundColor Green
                $fixResponse.fix_results.actions_taken | ForEach-Object { Write-Host "- $_" }
                
                Write-Host "`nRestarting LLM service to apply fixes..." -ForegroundColor Yellow
                docker restart rag_llm-service
                Write-Host "Waiting 10 seconds for service to restart..." -ForegroundColor Yellow
                Start-Sleep -Seconds 10
            }
            catch {
                Write-Host "Failed to fix metadata consumer: $_" -ForegroundColor Red
            }
        }
        else {
            Write-Host "`nMetadata consumer appears to be working correctly." -ForegroundColor Green
        }
    }
    catch {
        Write-Host "Failed to get metadata consumer diagnostics: $_" -ForegroundColor Red
    }
}
catch {
    Write-Host "Failed to connect to LLM service: $_" -ForegroundColor Red
    Write-Host "Restarting LLM service..." -ForegroundColor Yellow
    docker restart rag_llm-service
    Write-Host "Waiting 10 seconds for service to restart..." -ForegroundColor Yellow
    Start-Sleep -Seconds 10
}

# Final check on Kafka UI
Write-Host "`nChecking Kafka UI for consumer groups..." -ForegroundColor Yellow
Write-Host "Please check the Kafka UI at http://localhost:8180/ui/clusters/local/consumer-groups to verify consumers are now visible." -ForegroundColor Cyan
Write-Host "If no consumers appear, you may need to upload a document to trigger the metadata extraction process." -ForegroundColor Cyan

# Testing document upload
$testUpload = Read-Host "Would you like to upload a test document to trigger the metadata extraction process? (y/n)"
if ($testUpload -eq "y") {
    # Check if test document exists
    $testDocPath = "e:\code\experimental\RAG\test-file.txt"
    if (-not (Test-Path $testDocPath)) {
        # Create test document if it doesn't exist
        "This is a test document for metadata extraction." | Out-File $testDocPath
    }
    
    Write-Host "`nUploading test document..." -ForegroundColor Yellow
    try {
        $fileBytes = [System.IO.File]::ReadAllBytes($testDocPath)
        $fileEncoded = [System.Convert]::ToBase64String($fileBytes)
        $body = @{
            fileName = "test-file.txt"
            fileContent = $fileEncoded
            fileType = "text/plain"
        } | ConvertTo-Json
        
        $uploadResponse = Invoke-RestMethod -Uri "http://localhost/api/documents/upload" -Method Post -Body $body -ContentType "application/json" -ErrorAction Stop
        Write-Host "Document uploaded with ID: $($uploadResponse.documentId)" -ForegroundColor Green
        Write-Host "This should trigger the metadata extraction process." -ForegroundColor Green
        
        Write-Host "`nWaiting 10 seconds and checking Kafka consumer groups again..." -ForegroundColor Yellow
        Start-Sleep -Seconds 10
        docker exec rag_kafka kafka-consumer-groups --list --bootstrap-server kafka:29092
    }
    catch {
        Write-Host "Failed to upload test document: $_" -ForegroundColor Red
    }
}

Write-Host "`nDiagnostic process complete." -ForegroundColor Cyan
Write-Host "If issues persist, check the logs with: docker logs rag_llm-service" -ForegroundColor Cyan
