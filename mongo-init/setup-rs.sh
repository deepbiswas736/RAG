#!/bin/bash

# Script to initialize MongoDB replica set
echo "Starting MongoDB replica set initialization..."

# Check if MongoDB pods are up using our check script
if [ -f /scripts/check-pods.sh ]; then
    chmod +x /scripts/check-pods.sh
    /scripts/check-pods.sh
    if [ $? -ne 0 ]; then
        echo "MongoDB pods are not ready. Exiting."
        exit 1
    fi
else
    echo "Warning: check-pods.sh not found. Proceeding anyway..."
fi

# Initialize replica set configuration
echo "Initializing replica set..."
mongosh --host mongodb:27017 -u user -p password --authenticationDatabase admin --eval '
  if (rs.status().code == 94) {
    print("Initializing replica set for the first time...");
    rs.initiate({
      _id: "rs0",
      members: [
        { _id: 0, host: "mongodb:27017", priority: 1 }
      ]
    });
    print("Replica set initialized.");
  } else {
    print("Replica set already initialized or not in expected state:");
    printjson(rs.status());
  }
'

# Wait for the replica set to stabilize
echo "Waiting for replica set to stabilize..."
sleep 5

# Check replica set status
echo "Checking replica set status..."
mongosh --host mongodb:27017 -u user -p password --authenticationDatabase admin --eval 'printjson(rs.status())'

echo "MongoDB replica set initialization completed."
