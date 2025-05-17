\
"""
Page Content Data Class
-----------------------
Domain value object representing extracted page content.
"""
from typing import Dict, Any

class PageContent:
    """Domain value object representing extracted page content"""

    def __init__(self, page_num: int, text: str, extraction_method: str):
        self.page_num = page_num
        self.text = text
        self.extraction_method = extraction_method  # 'pdf_extract' or 'ocr'

    @property
    def has_content(self) -> bool:
        """Check if the page has meaningful text content"""
        return bool(self.text and not self.text.isspace())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            'page': self.page_num,
            'text': self.text,
            'method': self.extraction_method
        }
