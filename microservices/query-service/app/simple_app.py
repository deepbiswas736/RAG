# Basic working app for the query service
from fastapi import FastAPI

# Create the app
app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Query Service API is running"}

@app.get("/health")
def health():
    return {"status": "healthy"}
