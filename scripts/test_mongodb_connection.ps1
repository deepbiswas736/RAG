# PowerShell script to test MongoDB replica set connection

$connectionString = "mongodb://user:password@mongodb:27017/test?authSource=admin&replicaSet=rs0&retryWrites=true"

Write-Host "Testing connection to MongoDB replica set..." -ForegroundColor Cyan

# MongoDB connection test command
$testScript = @'
try {
  // Print replica set status
  print("Checking replica set status...");
  const status = rs.status();
  print("ReplicaSet status: " + (status.ok === 1 ? "OK" : "Error"));
  
  // Check authentication
  print("Testing authentication...");
  const authTest = db.runCommand({connectionStatus: 1});
  print("Authentication status: " + (authTest.ok === 1 ? "OK" : "Error"));
  print("Authenticated user: " + authTest.authInfo.authenticatedUserName);
  
  // Test database operations
  print("Testing database operations...");
  db = db.getSiblingDB("test_db");
  db.createCollection("test_collection");
  db.test_collection.insertOne({test: "data", timestamp: new Date()});
  const result = db.test_collection.find().toArray();
  print("Successfully wrote and read data from the database");
  print("Data: " + JSON.stringify(result));
  
  // Clean up
  db.test_collection.drop();
  print("Test completed successfully!");
} catch (e) {
  print("Error testing MongoDB connection:");
  print(e);
  quit(1);
}
'@

# Run test using docker
$testResult = docker run --rm --network rag_default mongo:latest mongosh "$connectionString" --eval "$testScript"

Write-Host "Test Results:" -ForegroundColor Green
$testResult

Write-Host "Connection test completed." -ForegroundColor Cyan
