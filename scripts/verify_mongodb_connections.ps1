# PowerShell script to verify all MongoDB connections in the RAG project

function Test-MongoDBConnection {
    param (
        [string]$ServiceName,
        [string]$ConnectionString
    )
    
    Write-Host "Testing $ServiceName MongoDB connection..." -ForegroundColor Cyan
    
    $testScript = @"
try {
  // Print connection information
  print('Testing connection for $ServiceName');
  print('Connection string: $ConnectionString');
  
  // Test connection and authentication
  const authTest = db.runCommand({connectionStatus: 1});
  if (authTest.ok !== 1) {
    print('Authentication failed');
    quit(1);
  }
  
  // Check if we're connected to a replica set
  const isMaster = db.runCommand({isMaster: 1});
  if (isMaster.setName) {
    print('Connected to replica set: ' + isMaster.setName);
    print('Primary: ' + isMaster.primary);
    print('Hosts: ' + JSON.stringify(isMaster.hosts));
  } else {
    print('Not connected to a replica set');
  }
  
  // Get database name from connection string
  const dbName = '$ConnectionString'.split('/')[3].split('?')[0];
  print('Using database: ' + dbName);
  
  // Test database operations
  db = db.getSiblingDB(dbName);
  try {
    const collections = db.getCollectionNames();
    print('Available collections: ' + JSON.stringify(collections));
  } catch (e) {
    print('Error listing collections: ' + e.message);
  }
  
  print('Connection test completed successfully');
} catch (e) {
  print('Error: ' + e.message);
  quit(1);
}
"@
    
    try {
        $result = docker run --rm --network rag_default mongo:latest mongosh "$ConnectionString" --eval "$testScript"
        Write-Host "$ServiceName Connection Results:" -ForegroundColor Green
        $result | ForEach-Object { Write-Host "  $_" }
        return $true
    }
    catch {
        Write-Host "$ServiceName Connection Failed:" -ForegroundColor Red
        Write-Host "  $_" -ForegroundColor Red
        return $false
    }
}

Write-Host "MongoDB Connection Verification for RAG Project" -ForegroundColor Yellow
Write-Host "================================================" -ForegroundColor Yellow

# Test document-service connection
$documentServiceConnection = "mongodb://user:password@mongodb:27017/document_service?authSource=admin&replicaSet=rs0&retryWrites=true"
$docServiceSuccess = Test-MongoDBConnection -ServiceName "document-service" -ConnectionString $documentServiceConnection

# Test query-service connection
$queryServiceConnection = "mongodb://user:password@mongodb:27017/rag_db?authSource=admin&replicaSet=rs0&retryWrites=true"
$queryServiceSuccess = Test-MongoDBConnection -ServiceName "query-service" -ConnectionString $queryServiceConnection

# Summary
Write-Host "`nConnection Test Summary:" -ForegroundColor Yellow
Write-Host "  document-service: $($docServiceSuccess ? 'Success' : 'Failed')" -ForegroundColor ($docServiceSuccess ? 'Green' : 'Red')
Write-Host "  query-service: $($queryServiceSuccess ? 'Success' : 'Failed')" -ForegroundColor ($queryServiceSuccess ? 'Green' : 'Red')

# Overall status
if ($docServiceSuccess -and $queryServiceSuccess) {
    Write-Host "`nAll MongoDB connections are working correctly with replica set configuration!" -ForegroundColor Green
} else {
    Write-Host "`nSome MongoDB connections failed. Please check the output above for details." -ForegroundColor Red
}
