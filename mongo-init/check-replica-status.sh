#!/bin/bash

echo "Checking MongoDB replica set status..."

# Try to connect and check replica set status
mongosh --quiet --eval '
  try {
    const status = rs.status();
    if(status.ok === 1) {
      print("Replica set is healthy!");
      print("Replica set name: " + status.set);
      print("Members:");
      status.members.forEach(function(member) {
        const state = member.stateStr;
        const name = member.name;
        const health = member.health ? "healthy" : "unhealthy";
        print(" - " + name + ": " + state + " (" + health + ")");
      });
      print("✓ Replica set is fully operational");
    } else {
      print("Replica set is not healthy. Status code: " + status.ok);
      printjson(status);
    }
  } catch (e) {
    print("Error checking replica set status: " + e.message);
    print("This could indicate that the replica set is not initialized.");
    print("Try running the initialization script first.");
  }
'

exit 0
