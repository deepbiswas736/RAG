#!/bin/bash
set -e

# This script ensures proper order of MongoDB initialization
# It's recommended to use this as part of the docker-entrypoint-initdb.d execution

echo "Starting MongoDB initialization process..."

# First initialize replica set
echo "Initializing replica set..."
mongosh --quiet /docker-entrypoint-initdb.d/init-replica.js

# Wait for replica set to stabilize
echo "Waiting for replica set to stabilize..."
sleep 5

# Then run the main initialization script
echo "Running main initialization script..."
mongosh --quiet /docker-entrypoint-initdb.d/init-mongo.js

echo "MongoDB initialization completed successfully"
