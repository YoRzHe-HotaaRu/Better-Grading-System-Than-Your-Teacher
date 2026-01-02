"""
Document Extraction Module.

Provides unified interface for extracting text from multiple document formats:
- PDF (.pdf)
- Word (.docx, .doc)
- Excel (.xlsx, .xls)
- Plain text (.txt, .md)
"""

from src.extractors.base import DocumentExtractor, ExtractionError
from src.extractors.factory import create_extractor, extract_document

__all__ = [
    "DocumentExtractor",
    "ExtractionError",
    "create_extractor",
    "extract_document",
]
