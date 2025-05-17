# PowerShell script to check MongoDB replica set status
Write-Host "Checking MongoDB replica set status..." -ForegroundColor Cyan

# Function to handle errors
function Handle-Error {
    param (
        [string]$ErrorMessage
    )
    Write-Host "Error: $ErrorMessage" -ForegroundColor Red
    exit 1
}

# Check if MongoDB container is running
try {
    $mongoContainer = docker ps --filter "name=mongodb" --format "{{.Names}}" | Where-Object { $_ }
    if (-not $mongoContainer) {
        Handle-Error "MongoDB container is not running. Please start the containers with 'docker-compose up -d'"
    }
    Write-Host "✓ MongoDB container is running: $mongoContainer" -ForegroundColor Green
}
catch {
    Handle-Error "Failed to check if MongoDB container is running: $_"
}

# Check MongoDB connection and replica set status
try {
    Write-Host "Checking MongoDB replica set status..." -ForegroundColor Cyan
    $replicaSetStatus = docker exec $mongoContainer mongosh --quiet --eval "JSON.stringify(rs.status())" | ConvertFrom-Json
    
    if ($replicaSetStatus.ok -eq 1) {
        Write-Host "✓ Replica set is initialized and working properly" -ForegroundColor Green
        Write-Host "Replica Set Name: $($replicaSetStatus.set)" -ForegroundColor Cyan
        Write-Host "Members:" -ForegroundColor Cyan
        
        foreach ($member in $replicaSetStatus.members) {
            $state = switch ($member.state) {
                1 { "PRIMARY" }
                2 { "SECONDARY" }
                7 { "ARBITER" }
                default { "OTHER ($($member.state))" }
            }
            Write-Host "  - $($member.name): $state" -ForegroundColor $(if ($member.state -eq 1) { "Yellow" } else { "White" })
        }
    } else {
        Handle-Error "Replica set is not properly initialized. Status code: $($replicaSetStatus.ok), Error: $($replicaSetStatus.errmsg)"
    }
}
catch {
    Handle-Error "Failed to check replica set status: $_"
}

# Check database and collections
try {
    Write-Host "Checking database and collections..." -ForegroundColor Cyan
    
    $dbList = docker exec $mongoContainer mongosh --quiet --eval "JSON.stringify(db.adminCommand('listDatabases'))" | ConvertFrom-Json
    
    if ($dbList.databases | Where-Object { $_.name -eq "rag_db" }) {
        Write-Host "✓ Database 'rag_db' exists" -ForegroundColor Green
        
        $collections = docker exec $mongoContainer mongosh "rag_db" --quiet --eval "JSON.stringify(db.getCollectionNames())" | ConvertFrom-Json
        
        if ($collections -contains "documents" -and $collections -contains "embeddings") {
            Write-Host "✓ Required collections exist: documents, embeddings" -ForegroundColor Green
        } else {
            Write-Host "! Some required collections are missing" -ForegroundColor Yellow
            Write-Host "  Available collections: $($collections -join ', ')" -ForegroundColor White
        }
    } else {
        Write-Host "! Database 'rag_db' does not exist" -ForegroundColor Yellow
        Write-Host "  Available databases: $($dbList.databases.name -join ', ')" -ForegroundColor White
    }
}
catch {
    Handle-Error "Failed to check database and collections: $_"
}

# Check vector search index
try {
    Write-Host "Checking vector search index..." -ForegroundColor Cyan
    
    $indexInfo = docker exec $mongoContainer mongosh "rag_db" --quiet --eval "JSON.stringify(db.embeddings.getIndexes())" | ConvertFrom-Json
    
    if ($indexInfo | Where-Object { $_.name -eq "vector_index" }) {
        Write-Host "✓ Vector search index exists and is configured" -ForegroundColor Green
        $vectorIndex = $indexInfo | Where-Object { $_.name -eq "vector_index" }
        Write-Host "  Index dimension: $($vectorIndex.vectorSearchOptions.dimension)" -ForegroundColor Cyan
        Write-Host "  Similarity metric: $($vectorIndex.vectorSearchOptions.similarity)" -ForegroundColor Cyan
    } else {
        Write-Host "! Vector search index is missing" -ForegroundColor Yellow
        Write-Host "  Available indexes: $($indexInfo.name -join ', ')" -ForegroundColor White
    }
}
catch {
    Write-Host "! Could not check vector search index: $_" -ForegroundColor Yellow
}

Write-Host "`nMongoDB setup check completed!" -ForegroundColor Cyan
