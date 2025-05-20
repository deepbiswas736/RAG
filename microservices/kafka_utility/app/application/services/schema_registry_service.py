"""
Schema Registry Service

This service manages message schemas and provides validation capabilities for Kafka messages.
It loads schemas from the domain/schemas directory and makes them available for validation.
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, Optional
import jsonschema
from pathlib import Path

logger = logging.getLogger(__name__)

class SchemaRegistryService:
    """
    Service for managing and validating message schemas.
    """
    
    def __init__(self, schema_dir: Optional[str] = None):
        """
        Initialize the schema registry.
        
        Args:
            schema_dir: Optional directory containing JSON Schema files.
                        Defaults to domain/schemas relative to the module.
        """
        if schema_dir is None:
            # Default to domain/schemas directory relative to this file
            base_dir = Path(__file__).parent.parent.parent
            self.schema_dir = base_dir / "domain" / "schemas"
        else:
            self.schema_dir = Path(schema_dir)
            
        self.schemas: Dict[str, Dict[str, Any]] = {}
    
    async def initialize(self) -> None:
        """
        Load all schema files from the schema directory.
        """
        try:
            logger.info(f"Loading schemas from {self.schema_dir}")
            
            if not self.schema_dir.exists():
                logger.error(f"Schema directory does not exist: {self.schema_dir}")
                return
            
            # Load all JSON schema files
            for schema_file in self.schema_dir.glob("*.json"):
                try:
                    schema_name = schema_file.stem
                    with open(schema_file, "r") as f:
                        schema = json.load(f)
                    
                    # Validate the schema itself
                    jsonschema.Draft7Validator.check_schema(schema)
                    
                    # Store the schema
                    self.schemas[schema_name] = schema
                    logger.info(f"Loaded schema: {schema_name}")
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON schema in {schema_file}: {e}")
                except jsonschema.exceptions.SchemaError as e:
                    logger.error(f"Invalid schema definition in {schema_file}: {e}")
                except Exception as e:
                    logger.error(f"Error loading schema from {schema_file}: {e}")
            
            logger.info(f"Loaded {len(self.schemas)} schemas")
        except Exception as e:
            logger.error(f"Failed to initialize schema registry: {e}")
    
    def validate(self, message: Dict[str, Any], schema_name: str) -> bool:
        """
        Validate a message against a named schema.
        
        Args:
            message: The message to validate
            schema_name: The name of the schema to validate against
            
        Returns:
            True if the message is valid, False otherwise
        """
        if schema_name not in self.schemas:
            logger.error(f"Schema not found: {schema_name}")
            return False
            
        try:
            jsonschema.validate(instance=message, schema=self.schemas[schema_name])
            return True
        except jsonschema.exceptions.ValidationError as e:
            logger.error(f"Message validation failed for schema {schema_name}: {e}")
            return False
    
    def get_schema(self, schema_name: str) -> Optional[Dict[str, Any]]:
        """
        Get a schema by name.
        
        Args:
            schema_name: The name of the schema to retrieve
            
        Returns:
            The schema dictionary, or None if not found
        """
        return self.schemas.get(schema_name)
