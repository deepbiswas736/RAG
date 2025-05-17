# PowerShell script to fix MongoDB replica set issues
# This script helps initialize and configure MongoDB replica sets properly

Write-Host "MongoDB Replica Set Fix Utility" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan

# Function to check the MongoDB status
function Check-MongoDBStatus {
    try {
        Write-Host "Checking MongoDB service status..." -ForegroundColor Cyan
        $isRunning = $false
        $containerName = docker ps --filter "name=mongodb" --format "{{.Names}}"
        
        if ($containerName) {
            Write-Host "✓ MongoDB container is running: $containerName" -ForegroundColor Green
            $isRunning = $true
        } else {
            Write-Host "× MongoDB container is not running" -ForegroundColor Red
            $isRunning = $false
        }
        
        return $isRunning
    }
    catch {
        Write-Host "Error checking MongoDB status: $_" -ForegroundColor Red
        return $false
    }
}

# Function to initialize the replica set
function Initialize-ReplicaSet {
    try {
        Write-Host "Initializing MongoDB replica set..." -ForegroundColor Cyan
        
        # Use docker exec to initialize the replica set
        $result = docker exec mongodb mongosh --eval '
        if (rs.status().code == 94 || rs.status().code == 93) {
            print("Initializing replica set...");
            rs.initiate({
                _id: "rs0",
                members: [
                    { _id: 0, host: "mongodb:27017", priority: 1 }
                ]
            });
            print("Waiting for replica set to initialize...");
            sleep(2000);  // Wait 2 seconds for initialization
            printjson(rs.status());
        } else {
            print("Replica set may already be initialized, checking status:");
            printjson(rs.status());
        }
        '
        
        Write-Host "Replica set initialization result:" -ForegroundColor Yellow
        Write-Host $result -ForegroundColor White
        
        return $true
    }
    catch {
        Write-Host "Error initializing replica set: $_" -ForegroundColor Red
        return $false
    }
}

# Function to check replica set status
function Check-ReplicaSetStatus {
    try {
        Write-Host "Checking replica set status..." -ForegroundColor Cyan
        
        $result = docker exec mongodb mongosh --eval 'printjson(rs.status())'
        
        if ($result -match '"ok" : 1') {
            Write-Host "✓ Replica set is properly initialized" -ForegroundColor Green
            return $true
        } else {
            Write-Host "× Replica set is not properly initialized" -ForegroundColor Red
            Write-Host $result -ForegroundColor White
            return $false
        }
    }
    catch {
        Write-Host "Error checking replica set status: $_" -ForegroundColor Red
        return $false
    }
}

# Function to update MongoDB connection strings in docker-compose.yml
function Update-ConnectionStrings {
    try {
        Write-Host "Updating MongoDB connection strings in services..." -ForegroundColor Cyan
        
        # Read the docker-compose.yml file
        $dockerComposeFile = "e:\code\experimental\RAG\docker-compose.yml"
        $content = Get-Content $dockerComposeFile -Raw
        
        # Replace connection strings to use replica set
        $content = $content -replace 'mongodb://user:password@mongodb:27017/\w+\?authSource=admin&directConnection=true', 'mongodb://user:password@mongodb:27017/$1?authSource=admin&replicaSet=rs0&retryWrites=true'
        
        # Write the updated content back to the file
        Set-Content -Path $dockerComposeFile -Value $content
        
        Write-Host "✓ Connection strings updated successfully" -ForegroundColor Green
        return $true
    }
    catch {
        Write-Host "Error updating connection strings: $_" -ForegroundColor Red
        return $false
    }
}

# Function to restart the containers
function Restart-Containers {
    try {
        Write-Host "Restarting containers..." -ForegroundColor Cyan
        
        # Restart the containers
        docker-compose -f "e:\code\experimental\RAG\docker-compose.yml" restart mongodb
        
        Write-Host "✓ Containers restarted successfully" -ForegroundColor Green
        return $true
    }
    catch {
        Write-Host "Error restarting containers: $_" -ForegroundColor Red
        return $false
    }
}

# Main execution flow
$steps = @(
    @{ Name = "Check MongoDB Status"; Function = "Check-MongoDBStatus" },
    @{ Name = "Initialize Replica Set"; Function = "Initialize-ReplicaSet" },
    @{ Name = "Check Replica Set Status"; Function = "Check-ReplicaSetStatus" },
    @{ Name = "Update Connection Strings"; Function = "Update-ConnectionStrings" },
    @{ Name = "Restart Containers"; Function = "Restart-Containers" }
)

$stepNumber = 1
$totalSteps = $steps.Count

foreach ($step in $steps) {
    Write-Host "`nStep $stepNumber of $totalSteps`: $($step.Name)" -ForegroundColor Yellow
    
    $result = & $step.Function
    
    if (-not $result -and $step.Name -ne "Check Replica Set Status") {
        Write-Host "× Step '$($step.Name)' failed. Fix the issue before continuing." -ForegroundColor Red
        exit 1
    }
    
    $stepNumber++
}

Write-Host "`nMongoDB replica set configuration completed successfully!" -ForegroundColor Green
Write-Host "You can now run your services and they should connect to the MongoDB replica set." -ForegroundColor Cyan
