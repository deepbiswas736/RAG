# PowerShell script to rollback from microservices to monolithic implementation
# Usage: .\rollback_migration.ps1
# Author: RAG Team
# Date: May 10, 2025

Write-Host "=== RAG System Rollback Tool ==="
Write-Host "Reverting from microservices to monolithic architecture"
Write-Host "-----------------------------------"

# Define paths
$BASE_PATH = "E:\code\experimental\RAG"
$DOCKER_COMPOSE_ORIGINAL = "$BASE_PATH\docker-compose.yml"
$DOCKER_COMPOSE_BACKUP = "$BASE_PATH\docker-compose.yml.bak"
$TRAEFIK_CONFIG_ORIGINAL = "$BASE_PATH\traefik\dynamic_conf.yml"
$TRAEFIK_CONFIG_BACKUP = "$BASE_PATH\traefik\dynamic_conf.yml.bak"

# Function to check if docker is running
function Test-DockerRunning {
    try {
        $dockerInfo = docker info 2>&1
        if ($LASTEXITCODE -eq 0) {
            return $true
        }
        else {
            return $false
        }
    }
    catch {
        return $false
    }
}

# Verify Docker is running
if (-not (Test-DockerRunning)) {
    Write-Host "ERROR: Docker is not running. Please start Docker and try again." -ForegroundColor Red
    exit 1
}

# Check if backup files exist
if (-not (Test-Path $DOCKER_COMPOSE_BACKUP)) {
    Write-Host "ERROR: Could not find the backup docker-compose file at $DOCKER_COMPOSE_BACKUP" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $TRAEFIK_CONFIG_BACKUP)) {
    Write-Host "ERROR: Could not find the backup Traefik config file at $TRAEFIK_CONFIG_BACKUP" -ForegroundColor Red
    exit 1
}

# Confirm with user
Write-Host "`nWARNING: This will roll back to the monolithic implementation. All microservices data may be lost." -ForegroundColor Yellow
$confirmation = Read-Host "Do you want to proceed? (y/n)"
if ($confirmation -ne 'y') {
    Write-Host "Rollback cancelled." -ForegroundColor Yellow
    exit 0
}

# Step 1: Stop current services
Write-Host "`nStopping current services..." -ForegroundColor Cyan
$currentDirectory = Get-Location
Set-Location $BASE_PATH
docker-compose down
Set-Location $currentDirectory
Write-Host "Current services stopped." -ForegroundColor Green

# Step 2: Restore original configuration
Write-Host "`nRestoring original configuration..." -ForegroundColor Cyan
Copy-Item -Path $DOCKER_COMPOSE_BACKUP -Destination $DOCKER_COMPOSE_ORIGINAL -Force
Copy-Item -Path $TRAEFIK_CONFIG_BACKUP -Destination $TRAEFIK_CONFIG_ORIGINAL -Force
Write-Host "Original configuration restored." -ForegroundColor Green

# Step 3: Start original services
Write-Host "`nStarting original monolithic services..." -ForegroundColor Cyan
$currentDirectory = Get-Location
Set-Location $BASE_PATH
docker-compose up -d
Set-Location $currentDirectory

# Step 4: Verify services are running
Write-Host "`nVerifying services..." -ForegroundColor Cyan
Start-Sleep -Seconds 10  # Wait for services to start

$currentDirectory = Get-Location
Set-Location $BASE_PATH
$runningContainers = docker-compose ps
Set-Location $currentDirectory

if ($runningContainers) {
    Write-Host "`nRollback completed successfully!" -ForegroundColor Green
    Write-Host "The RAG system is now running with the original monolithic architecture."
    Write-Host "`nImportant services:"
    Write-Host "- API: http://localhost/api/rag"
    Write-Host "- Document Processor: http://localhost/api/document-processor"
    Write-Host "- Traefik Dashboard: http://localhost:8080/"
}
else {
    Write-Host "`nWARNING: Some services might not have started correctly." -ForegroundColor Yellow
    Write-Host "Check the logs with: docker-compose logs -f"
}
