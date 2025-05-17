// MongoDB initialization script
print("Starting MongoDB initialization...");

// Verify replica set is working properly
print("Checking replica set status...");
try {
  const rsStatus = rs.status();
  print("Replica set status: " + rsStatus.ok);
  if (rsStatus.ok !== 1) {
    print("Warning: Replica set is not properly initialized!");
    printjson(rsStatus);
    throw new Error("Replica set initialization failed");
  } else {
    print("Replica set is properly initialized.");
  }
} catch (e) {
  print("Error checking replica set status: " + e.message);
  // Don't fail here, continue with initialization
}

// Connect to admin database
db = db.getSiblingDB('admin');
print("Connected to admin database");

// Create application user with appropriate permissions
db.createUser({
  user: "user",
  pwd: "password",
  roles: [
    { role: "readWrite", db: "rag_db" },
    { role: "dbAdmin", db: "rag_db" }
  ]
});
print("Created application user");

// Switch to the application database
db = db.getSiblingDB('rag_db');
print("Connected to rag_db database");

// Create collections
db.createCollection("documents");
db.createCollection("embeddings");
print("Created collections");

// Initialize vector search index if MongoDB supports it
try {
  db.embeddings.createIndex(
    { "vector": "vectorSearch" },
    { 
      name: "vector_index",
      vectorSearchOptions: { 
        dimension: 384,  // Adjust this based on your embedding model
        similarity: "cosine"
      }
    }
  );
  print("Created vector search index");
} catch (e) {
  print("Vector search index creation failed, may not be supported in this MongoDB version: " + e.message);
}

print("MongoDB initialization completed successfully");