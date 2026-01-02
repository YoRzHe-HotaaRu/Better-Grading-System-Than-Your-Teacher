"""
Extractor factory module.

Provides a factory function to select the appropriate extractor
based on file extension, and a convenience function for direct extraction.
"""

from pathlib import Path

from src.extractors.base import DocumentExtractor, ExtractionError
from src.extractors.docx_extractor import DocxExtractor
from src.extractors.excel_extractor import ExcelExtractor
from src.extractors.pdf_extractor import PDFExtractor
from src.extractors.text_extractor import TextExtractor
from src.models import ExtractedDocument

# Registry of all available extractors
_EXTRACTORS: tuple[type[DocumentExtractor], ...] = (
    PDFExtractor,
    DocxExtractor,
    ExcelExtractor,
    TextExtractor,
)


def get_supported_extensions() -> tuple[str, ...]:
    """
    Get all supported file extensions across all extractors.

    Returns:
        Tuple of supported extensions (e.g., ('.pdf', '.docx', ...)).
    """
    extensions: list[str] = []
    for extractor_cls in _EXTRACTORS:
        extensions.extend(extractor_cls.SUPPORTED_EXTENSIONS)
    return tuple(sorted(set(extensions)))


def create_extractor(file_path: Path | str) -> DocumentExtractor:
    """
    Create the appropriate extractor for a given file.

    Args:
        file_path: Path to the file to extract.

    Returns:
        An instance of the appropriate DocumentExtractor subclass.

    Raises:
        ExtractionError: If the file format is not supported.
    """
    path = Path(file_path) if isinstance(file_path, str) else file_path
    extension = path.suffix.lower()

    for extractor_cls in _EXTRACTORS:
        if extension in extractor_cls.SUPPORTED_EXTENSIONS:
            return extractor_cls()

    supported = get_supported_extensions()
    raise ExtractionError(
        f"Unsupported file format '{extension}'. Supported formats: {supported}",
        path,
    )


def extract_document(file_path: Path | str) -> ExtractedDocument:
    """
    Extract text from a document file.

    Convenience function that creates the appropriate extractor
    and performs the extraction in one step.

    Args:
        file_path: Path to the document file.

    Returns:
        ExtractedDocument containing the extracted text.

    Raises:
        ExtractionError: If extraction fails.
    """
    path = Path(file_path) if isinstance(file_path, str) else file_path
    extractor = create_extractor(path)
    return extractor.extract(path)
