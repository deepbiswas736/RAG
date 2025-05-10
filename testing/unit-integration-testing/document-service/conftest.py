"""
Configure test environment
"""
import sys
import os
import pytest
import asyncio
from pathlib import Path

# Find the root of the project
root = Path(__file__).parent.parent.parent.parent

# Add microservices/document-service/app to sys.path
app_path = str(root / "microservices" / "document-service" / "app")
if app_path not in sys.path:
    sys.path.insert(0, app_path)

# Create a fixture for event loop
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
