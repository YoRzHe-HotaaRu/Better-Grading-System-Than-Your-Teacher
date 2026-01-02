"""
Base classes for document extraction.

Defines the abstract interface that all extractors must implement,
ensuring consistent behavior across different file formats.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from src.models import ExtractedDocument


class ExtractionError(Exception):
    """
    Raised when document extraction fails.

    Contains detailed information about the failure cause.
    """

    def __init__(self, message: str, file_path: str | Path, cause: Exception | None = None):
        self.file_path = str(file_path)
        self.cause = cause
        super().__init__(f"Failed to extract '{file_path}': {message}")


class DocumentExtractor(ABC):
    """
    Abstract base class for document extractors.

    All extractors must implement the `extract` method and declare
    which file extensions they support via `SUPPORTED_EXTENSIONS`.
    """

    # Class variable: each subclass must override with supported extensions
    SUPPORTED_EXTENSIONS: ClassVar[tuple[str, ...]] = ()

    @classmethod
    def supports(cls, file_path: Path) -> bool:
        """
        Check if this extractor supports the given file.

        Args:
            file_path: Path to the file to check.

        Returns:
            True if this extractor can handle the file format.
        """
        return file_path.suffix.lower() in cls.SUPPORTED_EXTENSIONS

    @abstractmethod
    def extract(self, file_path: Path) -> ExtractedDocument:
        """
        Extract text content from the document.

        Args:
            file_path: Path to the document file.

        Returns:
            ExtractedDocument containing the text content and metadata.

        Raises:
            ExtractionError: If extraction fails for any reason.
        """
        ...

    def _validate_file(self, file_path: Path) -> None:
        """
        Validate that the file exists and is supported.

        Args:
            file_path: Path to validate.

        Raises:
            ExtractionError: If file doesn't exist or isn't supported.
        """
        if not file_path.exists():
            raise ExtractionError("File does not exist", file_path)

        if not file_path.is_file():
            raise ExtractionError("Path is not a file", file_path)

        if not self.supports(file_path):
            raise ExtractionError(
                f"Unsupported file format. Expected one of: {self.SUPPORTED_EXTENSIONS}",
                file_path,
            )

    def _create_result(self, content: str, file_path: Path) -> ExtractedDocument:
        """
        Create an ExtractedDocument from extracted content.

        Args:
            content: The extracted text content.
            file_path: Path to the source file.

        Returns:
            ExtractedDocument instance.
        """
        return ExtractedDocument(
            content=content,
            source_path=str(file_path.resolve()),
            file_extension=file_path.suffix.lower(),
        )
