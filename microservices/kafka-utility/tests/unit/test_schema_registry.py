"""
Tests for the SchemaRegistryService.
"""

import os
import json
import pytest
import tempfile
from pathlib import Path

from app.application.services.schema_registry_service import SchemaRegistryService


@pytest.fixture
def temp_schema_dir():
    """Create a temporary directory for test schemas."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a valid schema
        with open(os.path.join(temp_dir, "test_schema.json"), "w") as f:
            json.dump({
                "$schema": "http://json-schema.org/draft-07/schema#",
                "title": "Test Schema",
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "value": {"type": "number"}
                },
                "required": ["id"]
            }, f)
            
        # Create an invalid schema
        with open(os.path.join(temp_dir, "invalid_schema.json"), "w") as f:
            f.write("{not valid json")
        
        yield temp_dir


@pytest.mark.asyncio
async def test_schema_registry_initialization(temp_schema_dir):
    """Test that the schema registry can load schemas."""
    registry = SchemaRegistryService(schema_dir=temp_schema_dir)
    await registry.initialize()
    
    # Should have loaded the valid schema
    assert "test_schema" in registry.schemas
    assert registry.schemas["test_schema"]["title"] == "Test Schema"
    
    # Should not have loaded the invalid schema
    assert "invalid_schema" not in registry.schemas


@pytest.mark.asyncio
async def test_schema_validation(temp_schema_dir):
    """Test schema validation."""
    registry = SchemaRegistryService(schema_dir=temp_schema_dir)
    await registry.initialize()
    
    # Valid message
    valid_message = {"id": "123", "value": 42}
    assert registry.validate(valid_message, "test_schema") is True
    
    # Invalid message - missing required field
    invalid_message = {"value": 42}
    assert registry.validate(invalid_message, "test_schema") is False
    
    # Invalid message - wrong type
    invalid_type = {"id": "123", "value": "not a number"}
    assert registry.validate(invalid_type, "test_schema") is False
    
    # Non-existent schema
    assert registry.validate(valid_message, "non_existent") is False


@pytest.mark.asyncio
async def test_get_schema(temp_schema_dir):
    """Test getting a schema by name."""
    registry = SchemaRegistryService(schema_dir=temp_schema_dir)
    await registry.initialize()
    
    # Valid schema
    schema = registry.get_schema("test_schema")
    assert schema is not None
    assert schema["title"] == "Test Schema"
    
    # Non-existent schema
    assert registry.get_schema("non_existent") is None
