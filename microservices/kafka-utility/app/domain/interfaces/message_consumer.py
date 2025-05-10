"""
Message Consumer Interface

Defines the interface for consuming messages from Kafka.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Callable, Awaitable


class MessageConsumer(ABC):
    """Interface for consuming messages from Kafka."""
    
    @abstractmethod
    async def start_consuming(self) -> None:
        """Start consuming messages from Kafka."""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """Stop consuming messages from Kafka."""
        pass
    
    @abstractmethod
    def register_handler(self, topic: str, 
                        handler: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        """
        Register a handler for a topic.
        
        Args:
            topic: The topic to handle
            handler: The handler function that will be called with the message value
        """
        pass
