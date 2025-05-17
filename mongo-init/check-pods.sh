#!/bin/bash

# Script to check if MongoDB pods are up and ready
echo "Checking if MongoDB pods are running..."

# Maximum number of retries
MAX_RETRIES=30
RETRY_INTERVAL=5
counter=0

# Check if MongoDB is ready using the healthcheck command
while [ $counter -lt $MAX_RETRIES ]; do
    echo "Attempt $((counter+1))/$MAX_RETRIES: Checking MongoDB connection..."
    
    # Try to connect to MongoDB
    if mongosh "mongodb://user:password@mongodb:27017/admin" --eval "db.adminCommand('ping')" --quiet; then
        echo "MongoDB is up and running!"
        exit 0
    else
        echo "MongoDB is not ready yet. Retrying in $RETRY_INTERVAL seconds..."
        sleep $RETRY_INTERVAL
        counter=$((counter+1))
    fi
done

echo "Failed to connect to MongoDB after $MAX_RETRIES attempts."
exit 1
