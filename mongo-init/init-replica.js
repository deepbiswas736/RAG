// MongoDB replica set initialization script
print("Starting MongoDB replica set initialization...");

// Check if replica set is already initialized
try {
  const status = rs.status();
  print("Replica set is already initialized:");
  printjson(status);
} catch (e) {
  if (e.code == 94 || e.codeName == "NotYetInitialized") {
    print("Initializing replica set for the first time...");
    
    // Initialize the replica set
    const rsConfig = {
      _id: "rs0",
      members: [
        { _id: 0, host: "mongodb:27017", priority: 1 }
      ]
    };
    
    rs.initiate(rsConfig);
    
    // Wait for replica set to initialize
    print("Waiting for replica set to initialize...");
    
    // Sleep for a few seconds
    sleep(5000);
    
    // Check status after initialization
    const newStatus = rs.status();
    print("Replica set initialization result:");
    printjson(newStatus);
  } else {
    print("Error checking replica set status: " + e.message);
    printjson(e);
  }
}

// Connect to the admin database
print("Connecting to admin database...");
var adminDb = db.getSiblingDB('admin');

// Check if the user already exists to avoid duplicate user creation errors
var users = adminDb.getUsers();
var userExists = false;

for (var i = 0; i < users.users.length; i++) {
  if (users.users[i].user === "user") {
    userExists = true;
    break;
  }
}

if (!userExists) {
  print("Creating application user...");
  adminDb.createUser({
    user: "user",
    pwd: "password",
    roles: [
      { role: "userAdminAnyDatabase", db: "admin" },
      { role: "readWriteAnyDatabase", db: "admin" },
      { role: "dbAdminAnyDatabase", db: "admin" },
      { role: "clusterAdmin", db: "admin" }
    ]
  });
  print("Application user created.");
} else {
  print("Application user already exists.");
}

print("MongoDB replica set initialization completed.");
