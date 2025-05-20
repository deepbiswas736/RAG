"""
Message Serialization Utilities

This module provides utilities for serializing and deserializing messages
with schema validation and versioning.
"""

import json
import logging
from typing import Dict, Any, Optional
from jsonschema import validate, ValidationError

from ...application.services.schema_registry_service import SchemaRegistryService

logger = logging.getLogger(__name__)

class MessageSerializer:
    """
    Helper for serializing and deserializing messages with schema validation.
    """
    
    def __init__(self, schema_registry: SchemaRegistryService):
        """
        Initialize the message serializer.
        
        Args:
            schema_registry: Schema registry service for validation
        """
        self.schema_registry = schema_registry
        
    def create_envelope(self, payload: Dict[str, Any], 
                       message_type: str, 
                       version: str = "1.0", 
                       metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create a message envelope with standard metadata.
        
        Args:
            payload: The message payload
            message_type: Type of message (used for schema validation)
            version: Schema version
            metadata: Additional metadata to include
            
        Returns:
            Message envelope with payload and metadata
        """
        # Standard envelope format
        envelope = {
            "metadata": {
                "messageType": message_type,
                "version": version,
                "timestamp": self._get_timestamp(),
            },
            "payload": payload
        }
        
        # Add additional metadata if provided
        if metadata:
            envelope["metadata"].update(metadata)
            
        return envelope
        
    def validate_message(self, message: Dict[str, Any], schema_name: str) -> bool:
        """
        Validate a message against a schema.
        
        Args:
            message: The message to validate
            schema_name: Name of the schema to validate against
            
        Returns:
            True if valid, False otherwise
        """
        try:
            # Get schema from registry
            schema = self.schema_registry.get_schema(schema_name)
            if not schema:
                logger.error(f"Schema not found: {schema_name}")
                return False
                
            # Validate message
            validate(instance=message, schema=schema)
            return True
        except ValidationError as e:
            logger.error(f"Message validation failed for {schema_name}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error validating message: {e}")
            return False
    
    def extract_payload(self, envelope: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract the payload from a message envelope.
        
        Args:
            envelope: Message envelope
            
        Returns:
            The payload from the envelope
        """
        if not isinstance(envelope, dict):
            raise ValueError("Envelope must be a dictionary")
            
        if "payload" not in envelope:
            raise ValueError("Invalid envelope format: missing 'payload'")
            
        return envelope["payload"]
    
    def get_message_type(self, envelope: Dict[str, Any]) -> Optional[str]:
        """
        Get the message type from an envelope.
        
        Args:
            envelope: Message envelope
            
        Returns:
            The message type, or None if not found
        """
        if not isinstance(envelope, dict):
            return None
            
        if "metadata" not in envelope or not isinstance(envelope["metadata"], dict):
            return None
            
        return envelope["metadata"].get("messageType")
    
    def get_message_version(self, envelope: Dict[str, Any]) -> Optional[str]:
        """
        Get the message version from an envelope.
        
        Args:
            envelope: Message envelope
            
        Returns:
            The message version, or None if not found
        """
        if not isinstance(envelope, dict):
            return None
            
        if "metadata" not in envelope or not isinstance(envelope["metadata"], dict):
            return None
            
        return envelope["metadata"].get("version")
        
    @staticmethod
    def _get_timestamp() -> int:
        """Get the current timestamp in milliseconds."""
        import time
        return int(time.time() * 1000)
