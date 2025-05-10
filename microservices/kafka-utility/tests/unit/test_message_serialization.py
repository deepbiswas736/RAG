"""
Tests for the MessageSerializer.
"""

import json
import pytest
from unittest.mock import MagicMock, patch
import tempfile
import os

from app.infrastructure.utils.message_serialization import MessageSerializer
from app.application.services.schema_registry_service import SchemaRegistryService


@pytest.fixture
def mock_schema_registry():
    """Create a mock schema registry."""
    registry = MagicMock(spec=SchemaRegistryService)
    
    # Setup mock validation behavior
    def mock_validate(message, schema_name):
        if schema_name == "valid_schema":
            return True
        return False
    
    registry.validate = MagicMock(side_effect=mock_validate)
    
    # Setup mock get_schema behavior
    test_schema = {
        "type": "object",
        "required": ["metadata", "payload"],
        "properties": {
            "metadata": {
                "type": "object",
                "required": ["messageType"]
            },
            "payload": {
                "type": "object"
            }
        }
    }
    
    def mock_get_schema(schema_name):
        if schema_name == "valid_schema":
            return test_schema
        return None
    
    registry.get_schema = MagicMock(side_effect=mock_get_schema)
    
    return registry


@pytest.fixture
def serializer(mock_schema_registry):
    """Create a MessageSerializer with a mock schema registry."""
    return MessageSerializer(schema_registry=mock_schema_registry)


def test_create_envelope(serializer):
    """Test creating a message envelope."""
    payload = {"id": "123", "value": 42}
    message_type = "test.event"
    version = "1.0"
    metadata = {"correlationId": "abc123"}
    
    envelope = serializer.create_envelope(
        payload=payload,
        message_type=message_type,
        version=version,
        metadata=metadata
    )
    
    assert envelope["payload"] == payload
    assert envelope["metadata"]["messageType"] == message_type
    assert envelope["metadata"]["version"] == version
    assert envelope["metadata"]["correlationId"] == "abc123"
    assert "timestamp" in envelope["metadata"]


def test_validate_message(serializer, mock_schema_registry):
    """Test message validation."""
    # Valid schema
    assert serializer.validate_message({"test": "message"}, "valid_schema") is True
    mock_schema_registry.get_schema.assert_called_with("valid_schema")
    
    # Invalid schema
    assert serializer.validate_message({"test": "message"}, "invalid_schema") is False
    mock_schema_registry.get_schema.assert_called_with("invalid_schema")


def test_extract_payload(serializer):
    """Test extracting payload from envelope."""
    payload = {"id": "123", "value": 42}
    envelope = {"metadata": {}, "payload": payload}
    
    extracted = serializer.extract_payload(envelope)
    assert extracted == payload
    
    # Test invalid envelope
    with pytest.raises(ValueError):
        serializer.extract_payload("not an envelope")
    
    with pytest.raises(ValueError):
        serializer.extract_payload({"metadata": {}})  # Missing payload


def test_get_message_type(serializer):
    """Test extracting message type from envelope."""
    envelope = {
        "metadata": {"messageType": "test.event"},
        "payload": {}
    }
    
    assert serializer.get_message_type(envelope) == "test.event"
    
    # Test invalid envelope
    assert serializer.get_message_type("not an envelope") is None
    assert serializer.get_message_type({"payload": {}}) is None
    assert serializer.get_message_type({"metadata": "not a dict"}) is None


def test_get_message_version(serializer):
    """Test extracting message version from envelope."""
    envelope = {
        "metadata": {"version": "1.0"},
        "payload": {}
    }
    
    assert serializer.get_message_version(envelope) == "1.0"
    
    # Test invalid envelope
    assert serializer.get_message_version("not an envelope") is None
    assert serializer.get_message_version({"payload": {}}) is None
    assert serializer.get_message_version({"metadata": "not a dict"}) is None
