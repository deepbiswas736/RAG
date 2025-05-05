// MongoDB initialization script
print("Starting MongoDB initialization...");

// Connect to admin database to create user
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