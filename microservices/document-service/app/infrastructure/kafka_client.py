from typing import Dict, Any

class KafkaClient:
    """Client for interacting with Kafka message broker"""
    
    async def send_metadata_extraction_request(self, document_id: str, document_path: str, file_type: str) -> None:
        """Send a request for metadata extraction"""
        raise NotImplementedError
        
    async def send_document_processed_event(self, document_id: str, status: str, metadata: Dict[str, Any]) -> None:
        """Send an event indicating document processing status"""
        raise NotImplementedError
