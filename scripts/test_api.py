import sys
import os

# Add the parent directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# Import the FastAPI app
from app.main import app
import uvicorn

if __name__ == "__main__":
    print("Starting FastAPI server...")
    print(f"Python path: {sys.path}")
    print(f"Current directory: {current_dir}")
    uvicorn.run(app, host="0.0.0.0", port=8000)