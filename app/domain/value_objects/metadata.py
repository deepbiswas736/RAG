from dataclasses import dataclass
from typing import Dict, Optional
from datetime import datetime

@dataclass(frozen=True)
class DocumentMetadata:
    file_type: str
    page_number: Optional[int]
    source_type: str  # 'text', 'image', 'pdf'
    processing_date: datetime
    additional_info: Dict

    @classmethod
    def from_dict(cls, data: Dict) -> 'DocumentMetadata':
        return cls(
            file_type=data.get('file_type', ''),
            page_number=data.get('page_number'),
            source_type=data.get('source_type', 'text'),
            processing_date=datetime.utcnow(),
            additional_info=data.get('additional_info', {})
        )