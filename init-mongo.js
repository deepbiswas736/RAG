// MongoDB initialization script for vector search
// This script automatically runs when the MongoDB container starts
// as it's mounted to /docker-entrypoint-initdb.d/

// Switch to admin database
db = db.getSiblingDB('admin');

// Create admin user if not created by init
try {
  // Check if any users exist
  const adminUsers = db.getUsers();
  if (adminUsers.users.length === 0) {
    print("Creating admin user...");
    db.createUser({
      user: "admin",
      pwd: "password",
      roles: ["root"]
    });
    print("Admin user created");
  } else {
    print("Admin users already exist");
  }
} catch (e) {
  print("Error checking admin users: " + e);
}

// Authenticate as admin
db.auth("admin", "password");

// Create application database
db = db.getSiblingDB('rag_db');

// Create application user
try {
  db.createUser({
    user: "app_user",
    pwd: "app_password",
    roles: [
      { role: "readWrite", db: "rag_db" }
    ]
  });
  print("Created application user for rag_db");
} catch (e) {
  print("Application user may already exist: " + e);
}

// Create collections
db.createCollection("documents");
db.createCollection("chunks");

// Create basic indexes
db.chunks.createIndex({ "content": "text" });
db.chunks.createIndex({ "metadata.document_id": 1 });

// Create vector search index using MongoDB 7.0+ native vector search
try {
  db.chunks.createIndex(
    { "embedding.vector": "vector" },
    {
      name: "vector_index",
      vectorOptions: {
        dimensions: 384,
        similarity: "cosine"
      }
    }
  );
  print("Vector search index created successfully");
} catch (e) {
  print("Error creating vector index: " + e);
  print("Note: If this is related to dimensions, ensure your vectors match the configured dimension");
}

print("MongoDB initialization complete");