#!/bin/bash
# Script to properly set up and initialize MongoDB with a replica set

# Sleep a bit to make sure MongoDB has time to start
echo "Waiting for MongoDB to start..."
sleep 10

echo "Initializing MongoDB replica set..."

# Attempt to initialize the replica set
docker exec rag-mongodb-1 mongosh --eval '
try {
  // Check if already initialized
  const status = rs.status();
  if (status.ok === 1) {
    print("Replica set is already initialized:");
    printjson(status);
  } else {
    print("Unexpected status: " + JSON.stringify(status));
  }
} catch (e) {
  // If we get here, the replica set has not been initialized
  if (e.codeName === "NotYetInitialized" || e.message.includes("no replset config")) {
    print("Initializing replica set rs0...");
    const config = {
      _id: "rs0",
      members: [
        { _id: 0, host: "mongodb:27017" }
      ]
    };
    const result = rs.initiate(config);
    print("Initialization result:");
    printjson(result);
    
    // Wait a moment for initialization to complete
    sleep(2000);
    
    // Check status again
    printjson(rs.status());
  } else {
    print("Unexpected error: " + e.message);
  }
}
'

echo "MongoDB replica set initialization completed."
echo "Testing connection with authentication..."

# Test connection with authentication
docker exec rag-mongodb-1 mongosh --eval '
try {
  db.getSiblingDB("admin").auth("user", "password");
  print("Authentication successful!");
  
  // Print replicaSet status
  const status = rs.status();
  print("ReplicaSet status:");
  printjson(status);
  
  // Create the application database if not exists
  db = db.getSiblingDB("rag_db");
  db.createCollection("test");
  print("Created test collection in rag_db");
  
  // Print database information
  const dbInfo = db.stats();
  print("Database info:");
  printjson(dbInfo);
} catch (e) {
  print("Error: " + e.message);
}
'

echo "MongoDB setup completed."
