#!/bin/bash

# MongoDB entrypoint script
echo "Starting MongoDB initialization process..."

# Create mongodb keyfile directory if it doesn't exist
if [ ! -d "/data/configdb/keyfile" ]; then
    mkdir -p /data/configdb/keyfile
    chmod 700 /data/configdb/keyfile
fi

# Copy keyfile if provided
if [ -f "/keyfile/mongodb-keyfile" ]; then
    cp /keyfile/mongodb-keyfile /data/configdb/keyfile/
    chmod 400 /data/configdb/keyfile/mongodb-keyfile
    chown 999:999 /data/configdb/keyfile/mongodb-keyfile
    echo "MongoDB keyfile installed."
fi

# Make scripts executable
chmod +x /docker-entrypoint-initdb.d/setup-rs.sh
chmod +x /docker-entrypoint-initdb.d/check-pods.sh

# Check if MongoDB pods are up
echo "Checking if MongoDB pods are ready..."
/docker-entrypoint-initdb.d/check-pods.sh
if [ $? -ne 0 ]; then
    echo "Error: MongoDB pods are not ready. Please check your MongoDB deployment."
    exit 1
fi

# Set up replica set
echo "Setting up MongoDB replica set..."
/docker-entrypoint-initdb.d/setup-rs.sh
if [ $? -ne 0 ]; then
    echo "Error: Failed to initialize replica set."
    exit 1
fi

# Run MongoDB initialization script
echo "Running MongoDB initialization script..."
mongosh mongodb://user:password@mongodb:27017/admin /docker-entrypoint-initdb.d/init-mongo.js

echo "MongoDB initialization process completed."
