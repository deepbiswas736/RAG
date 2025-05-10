from dataclasses import dataclass, field
from typing import Dict, Optional, List
from datetime import datetime

@dataclass
class DocumentMetadata:
    file_type: str = ""
    file_name: str = ""
    person_name: str = ""
    page_number: Optional[int] = None
    source_type: str = "text"  # 'text', 'image', 'pdf'
    processing_date: datetime = field(default_factory=datetime.utcnow)
    topics: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    entities: Dict[str, List[str]] = field(default_factory=dict)  # e.g., {"PERSON": ["John Doe"], "ORG": ["Acme Inc"]}
    summary: str = ""
    document_id: str = ""
    additional_info: Dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict) -> 'DocumentMetadata':
        metadata = cls(
            file_type=data.get('file_type', ''),
            file_name=data.get('file_name', ''),
            person_name=data.get('person_name', ''),
            page_number=data.get('page_number'),
            source_type=data.get('source_type', 'text'),
            document_id=data.get('document_id', ''),
            summary=data.get('summary', ''),
        )
        
        # Set processing_date if provided, otherwise use current time
        if 'processing_date' in data:
            metadata.processing_date = data['processing_date']
            
        # Handle list fields
        metadata.topics = data.get('topics', [])
        metadata.keywords = data.get('keywords', [])
        metadata.entities = data.get('entities', {})
        
        # Copy any additional fields to additional_info
        metadata.additional_info = {}
        for k, v in data.items():
            if k not in ['file_type', 'file_name', 'person_name', 'page_number', 
                         'source_type', 'processing_date', 'topics', 'keywords', 
                         'entities', 'summary', 'document_id', 'additional_info']:
                metadata.additional_info[k] = v
                
        return metadata