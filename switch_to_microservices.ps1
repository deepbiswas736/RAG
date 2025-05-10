# PowerShell script to migrate from monolithic to microservices implementation
# Usage: .\switch_to_microservices.ps1
# Author: RAG Team
# Date: May 10, 2025

Write-Host "=== RAG System Migration Tool ==="
Write-Host "Switching from monolithic to microservices architecture"
Write-Host "-----------------------------------"

# Define paths
$BASE_PATH = "E:\code\experimental\RAG"
# No longer needed as we're updating the existing docker-compose file directly

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

# Function to check if containers are running
function Get-RunningContainers {
    param (
        [string]$ComposeFile
    )
    
    $currentDirectory = Get-Location
    Set-Location $BASE_PATH
    
    try {
        $result = docker-compose -f $ComposeFile ps -q
        return $result
    }
    finally {
        Set-Location $currentDirectory
    }
}

# Verify Docker is running
if (-not (Test-DockerRunning)) {
    Write-Host "ERROR: Docker is not running. Please start Docker and try again." -ForegroundColor Red
    exit 1
}

# Confirm with user
Write-Host "`nWARNING: This will stop the current RAG application and switch to the microservices implementation." -ForegroundColor Yellow
$confirmation = Read-Host "Do you want to proceed? (y/n)"
if ($confirmation -ne 'y') {
    Write-Host "Migration cancelled." -ForegroundColor Yellow
    exit 0
}

# Step 1: Stop current services
Write-Host "`nStopping current services..." -ForegroundColor Cyan
$currentDirectory = Get-Location
Set-Location $BASE_PATH
docker-compose down
Set-Location $currentDirectory
Write-Host "Current services stopped." -ForegroundColor Green

# Step 2: Start new services
Write-Host "`nStarting microservices..." -ForegroundColor Cyan
$currentDirectory = Get-Location
Set-Location $BASE_PATH
docker-compose up -d
Set-Location $currentDirectory

# Step 3: Verify services are running
Write-Host "`nVerifying services..." -ForegroundColor Cyan
Start-Sleep -Seconds 10  # Wait for services to start

$currentDirectory = Get-Location
Set-Location $BASE_PATH
$runningContainers = docker-compose ps
Set-Location $currentDirectory

if ($runningContainers) {
    Write-Host "`nMigration completed successfully!" -ForegroundColor Green
    Write-Host "The RAG system is now running with the microservices architecture."
    Write-Host "`nImportant services:"
    Write-Host "- Document Service API: http://localhost/api/documents"
    Write-Host "- LLM Service API: http://localhost/api/llm"
    Write-Host "- Query Service API: http://localhost/api/query"
    Write-Host "- UI: http://localhost/"
    Write-Host "- Traefik Dashboard: http://localhost:8080/"    Write-Host "- Kafka UI: http://localhost:8180/"
    Write-Host "`nTo monitor logs: docker-compose logs -f [service-name]"
}
else {
    Write-Host "`nWARNING: Some services might not have started correctly." -ForegroundColor Yellow
    Write-Host "Check the logs with: docker-compose logs -f"
    Write-Host "To roll back: .\rollback_migration.ps1"
}
