# PowerShell script to check MongoDB replica set status
Write-Host "MongoDB Replica Set Status Check" -ForegroundColor Cyan
Write-Host "===============================" -ForegroundColor Cyan

# Check if MongoDB container is running
try {
    Write-Host "Checking MongoDB container status..." -ForegroundColor Cyan
    $mongoContainer = docker ps --filter "name=mongodb" --format "{{.Names}}"
    
    if (-not $mongoContainer) {
        Write-Host "× MongoDB container is not running" -ForegroundColor Red
        Write-Host "  Start the containers with 'docker-compose up -d'" -ForegroundColor Yellow
        exit 1
    }
    
    Write-Host "✓ MongoDB container is running: $mongoContainer" -ForegroundColor Green
}
catch {
    Write-Host "Error checking MongoDB container: $_" -ForegroundColor Red
    exit 1
}

# Check MongoDB replication status
try {
    Write-Host "`nChecking replica set status..." -ForegroundColor Cyan
    $replicaStatus = docker exec $mongoContainer mongosh --quiet --eval "JSON.stringify(rs.status())" | ConvertFrom-Json -ErrorAction SilentlyContinue
    
    if ($null -eq $replicaStatus) {
        Write-Host "× Failed to get replica set status. Is MongoDB running in replica set mode?" -ForegroundColor Red
        exit 1
    }
    
    if ($replicaStatus.ok -eq 1) {
        Write-Host "✓ Replica set is properly initialized" -ForegroundColor Green
        Write-Host "  Replica Set Name: $($replicaStatus.set)" -ForegroundColor Cyan
        Write-Host "  Members:" -ForegroundColor Cyan
        
        foreach ($member in $replicaStatus.members) {
            $state = switch ($member.state) {
                1 { "PRIMARY" }
                2 { "SECONDARY" }
                7 { "ARBITER" }
                default { "OTHER ($($member.state))" }
            }
            $stateColor = if ($state -eq "PRIMARY") { "Yellow" } else { "White" }
            Write-Host "   - $($member.name): $state" -ForegroundColor $stateColor
        }
    }
    else {
        Write-Host "× Replica set is not properly initialized" -ForegroundColor Red
        Write-Host "  Error: $($replicaStatus.errmsg)" -ForegroundColor Red
        Write-Host "  Run the fix_mongodb_replicaset.ps1 script to initialize the replica set" -ForegroundColor Yellow
        exit 1
    }
}
catch {
    Write-Host "Error checking replica set status: $_" -ForegroundColor Red
    Write-Host "Run the fix_mongodb_replicaset.ps1 script to initialize the replica set" -ForegroundColor Yellow
    exit 1
}

# Check connection strings in docker-compose.yml
Write-Host "`nChecking MongoDB connection strings in docker-compose.yml..." -ForegroundColor Cyan
try {
    $dockerComposeFile = "e:\code\experimental\RAG\docker-compose.yml"
    $content = Get-Content $dockerComposeFile -Raw
    
    $correctConnectionPatterns = @(
        'mongodb://user:password@mongodb:27017/\w+\?authSource=admin&replicaSet=rs0'
    )
    
    $incorrectConnectionPatterns = @(
        'mongodb://user:password@mongodb:27017/\w+\?authSource=admin&directConnection=true'
    )
    
    $hasIncorrectConnections = $false
    foreach ($pattern in $incorrectConnectionPatterns) {
        if ($content -match $pattern) {
            $hasIncorrectConnections = $true
            Write-Host "× Found incorrect connection string pattern: $pattern" -ForegroundColor Red
        }
    }
    
    if (-not $hasIncorrectConnections) {
        Write-Host "✓ Connection strings look good" -ForegroundColor Green
    }
    else {
        Write-Host "  Run the fix_mongodb_replicaset.ps1 script to update connection strings" -ForegroundColor Yellow
    }
}
catch {
    Write-Host "Error checking connection strings: $_" -ForegroundColor Red
}

# Attempt to test a connection to verify it's working
Write-Host "`nTesting MongoDB connection..." -ForegroundColor Cyan
try {
    $testConnection = docker exec $mongoContainer mongosh --quiet --eval '
    try {
        db = db.getSiblingDB("admin");
        db.auth("user", "password");
        db = db.getSiblingDB("rag_db");
        let result = db.runCommand({ ping: 1 });
        JSON.stringify({ success: result.ok === 1, message: "Connection successful" });
    } catch (e) {
        JSON.stringify({ success: false, message: e.message });
    }
    ' | ConvertFrom-Json
    
    if ($testConnection.success) {
        Write-Host "✓ Connection test successful" -ForegroundColor Green
    }
    else {
        Write-Host "× Connection test failed: $($testConnection.message)" -ForegroundColor Red
    }
}
catch {
    Write-Host "Error testing connection: $_" -ForegroundColor Red
}

Write-Host "`nMongoDB replica set status check completed!" -ForegroundColor Cyan
