"""
Kafka Health Service

This service monitors the health of Kafka connections and provides diagnostics.
"""

import os
import logging
import asyncio
import socket
from typing import List, Dict, Any, Optional
from aiokafka.admin import AIOKafkaAdminClient
from aiokafka.errors import KafkaError
from kafka.errors import KafkaConnectionError

logger = logging.getLogger(__name__)

class KafkaHealthService:
    """
    Service for monitoring Kafka health and connectivity.
    """
    
    def __init__(self, bootstrap_servers: str, connection_timeout: int = 5):
        """
        Initialize the Kafka health service.
        
        Args:
            bootstrap_servers: Kafka bootstrap servers, comma-separated
            connection_timeout: Connection timeout in seconds
        """
        self.bootstrap_servers = bootstrap_servers
        self.connection_timeout = connection_timeout
        self.admin_client = None
        self.last_health_status = False
    
    async def check_kafka_availability(self) -> bool:
        """
        Check if Kafka is available by establishing a connection.
        
        Returns:
            True if Kafka is available, False otherwise
        """
        try:
            # Try to create an admin client connection to check availability
            if self.admin_client is None:
                self.admin_client = AIOKafkaAdminClient(
                    bootstrap_servers=self.bootstrap_servers,
                    client_id="kafka-utility-health-checker",
                    request_timeout_ms=self.connection_timeout * 1000
                )
                await self.admin_client.start()
            
            # List topics to verify connection
            topics = await self.admin_client.list_topics()
            logger.info(f"Kafka health check successful, found {len(topics)} topics")
            
            # Update status
            self.last_health_status = True
            return True
            
        except KafkaConnectionError as e:
            logger.warning(f"Kafka connection failed: {e}")
            self.last_health_status = False
            
            # Clean up admin client on connection failure
            if self.admin_client:
                await self.admin_client.close()
                self.admin_client = None
            
            return False
        except Exception as e:
            logger.error(f"Kafka health check error: {e}")
            self.last_health_status = False
            
            # Clean up admin client on any error
            if self.admin_client:
                await self.admin_client.close()
                self.admin_client = None
            
            return False
    
    async def get_health_status(self) -> Dict[str, Any]:
        """
        Get detailed health status information.
        
        Returns:
            Dictionary with health status information
        """
        status = {
            "kafka_available": await self.check_kafka_availability(),
            "bootstrap_servers": self.bootstrap_servers,
        }
        
        if self.last_health_status and self.admin_client:
            try:
                # Get additional information if Kafka is available
                status["topics"] = await self.admin_client.list_topics()
                cluster_metadata = await self.admin_client.describe_cluster()
                status["cluster"] = {
                    "nodes": len(cluster_metadata.nodes),
                    "controller_id": cluster_metadata.controller_id
                }
            except Exception as e:
                logger.error(f"Error getting additional health status: {e}")
                status["error"] = str(e)
        
        return status
    
    async def close(self):
        """Close the admin client connection."""
        if self.admin_client:
            try:
                await self.admin_client.close()
                self.admin_client = None
            except Exception as e:
                logger.error(f"Error closing admin client: {e}")


if __name__ == "__main__":
    # Simple test for the health service
    async def test_health():
        logging.basicConfig(level=logging.INFO)
        bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        
        health_service = KafkaHealthService(bootstrap_servers=bootstrap_servers)
        available = await health_service.check_kafka_availability()
        
        print(f"Kafka available: {available}")
        if available:
            status = await health_service.get_health_status()
            print(f"Health status: {status}")
        
        await health_service.close()
    
    asyncio.run(test_health())
