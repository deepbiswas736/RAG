"""
Message Producer Interface

Defines the interface for producing messages to Kafka.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class MessageProducer(ABC):
    """Interface for producing messages to Kafka."""
    
    @abstractmethod
    async def send_message(self, topic: str, key: Optional[str], value: Dict[str, Any],
                           headers: Optional[Dict[str, str]] = None) -> bool:
        """
        Send a message to Kafka.
        
        Args:
            topic: The topic to send the message to
            key: The optional message key
            value: The message value
            headers: Optional message headers
            
        Returns:
            True if the message was sent successfully, False otherwise
        """
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close the producer."""
        pass
