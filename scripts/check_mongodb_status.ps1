# PowerShell script to check MongoDB status

Write-Host "Checking MongoDB status..." -ForegroundColor Cyan

# Check if MongoDB container is running
try {
    $mongoContainer = docker ps --filter "name=mongodb" --format "{{.Names}}"
    if (-not $mongoContainer) {
        Write-Host "Error: MongoDB container is not running!" -ForegroundColor Red
        Write-Host "Please start the containers with 'docker-compose up -d'" -ForegroundColor Yellow
        exit 1
    }
    
    Write-Host "MongoDB container is running: $mongoContainer" -ForegroundColor Green
    
    # Check replica set status
    Write-Host "`nChecking replica set status..." -ForegroundColor Cyan
    
    $replicaSetStatus = docker exec $mongoContainer mongosh --quiet --eval "JSON.stringify(rs.status())" | ConvertFrom-Json
    
    if ($replicaSetStatus.ok -eq 1) {
        Write-Host "✓ Replica set is initialized and working properly" -ForegroundColor Green
        Write-Host "Replica Set Name: $($replicaSetStatus.set)" -ForegroundColor Cyan
        Write-Host "Members:" -ForegroundColor Cyan
        
        foreach ($member in $replicaSetStatus.members) {
            $stateColor = switch ($member.stateStr) {
                "PRIMARY" { "Yellow" }
                "SECONDARY" { "Green" }
                default { "White" }
            }
            
            $healthStatus = if ($member.health -eq 1) { "healthy" } else { "unhealthy" }
            Write-Host "  - $($member.name): $($member.stateStr) ($healthStatus)" -ForegroundColor $stateColor
        }
        
        # Check if we can connect with authentication
        Write-Host "`nTesting authenticated connection..." -ForegroundColor Cyan
        $authTest = docker exec $mongoContainer mongosh --quiet "mongodb://user:password@mongodb:27017/admin" --eval "JSON.stringify({connected: true, auth: 'success'})"
        
        if ($authTest) {
            Write-Host "✓ Authentication is working properly" -ForegroundColor Green
        } else {
            Write-Host "! Authentication test failed" -ForegroundColor Red
        }
        
        # Check databases
        Write-Host "`nChecking databases..." -ForegroundColor Cyan
        $dbs = docker exec $mongoContainer mongosh --quiet "mongodb://user:password@mongodb:27017/admin" --eval "JSON.stringify(db.adminCommand('listDatabases'))" | ConvertFrom-Json
        
        Write-Host "Available databases:" -ForegroundColor Cyan
        foreach ($database in $dbs.databases) {
            Write-Host "  - $($database.name) ($([Math]::Round($database.sizeOnDisk / 1024 / 1024, 2)) MB)" -ForegroundColor White
        }
        
    } else {
        Write-Host "! Replica set is not initialized properly" -ForegroundColor Red
        Write-Host "Error code: $($replicaSetStatus.code), Message: $($replicaSetStatus.codeName)" -ForegroundColor Red
        
        Write-Host "`nTrying to initialize replica set..." -ForegroundColor Yellow
        $initResult = docker exec $mongoContainer mongosh --quiet --eval "JSON.stringify(rs.initiate({_id: 'rs0', members: [{_id: 0, host: 'mongodb:27017'}]}))"
        
        if ($initResult) {
            $parsed = $initResult | ConvertFrom-Json
            if ($parsed.ok -eq 1) {
                Write-Host "✓ Replica set initialized successfully!" -ForegroundColor Green
                Write-Host "Please wait a moment for it to stabilize, then run this script again." -ForegroundColor Yellow
            } else {
                Write-Host "! Failed to initialize replica set: $($parsed.errmsg)" -ForegroundColor Red
            }
        }
    }
    
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
    Write-Host "Try running 'docker-compose down' and then 'docker-compose up -d' to restart the containers." -ForegroundColor Yellow
}
