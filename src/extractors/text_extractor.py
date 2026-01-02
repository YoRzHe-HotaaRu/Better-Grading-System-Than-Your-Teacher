"""
Plain text document extractor.

Handles .txt and .md files with proper encoding detection.
"""

from pathlib import Path
from typing import ClassVar

from src.extractors.base import DocumentExtractor, ExtractionError
from src.models import ExtractedDocument


class TextExtractor(DocumentExtractor):
    """
    Extracts text from plain text files.

    Handles .txt and .md files with UTF-8 encoding (with fallback options).
    """

    SUPPORTED_EXTENSIONS: ClassVar[tuple[str, ...]] = (".txt", ".md")

    # Encodings to try in order of preference
    ENCODINGS: ClassVar[tuple[str, ...]] = ("utf-8", "utf-8-sig", "latin-1", "cp1252")

    def extract(self, file_path: Path) -> ExtractedDocument:
        """
        Extract text from a plain text file.

        Args:
            file_path: Path to the text file.

        Returns:
            ExtractedDocument with the file content.

        Raises:
            ExtractionError: If the file cannot be read.
        """
        self._validate_file(file_path)

        content = self._read_with_encoding_fallback(file_path)

        if not content.strip():
            raise ExtractionError("File is empty or contains only whitespace", file_path)

        return self._create_result(content, file_path)

    def _read_with_encoding_fallback(self, file_path: Path) -> str:
        """
        Read file content with encoding fallback.

        Tries multiple encodings until one succeeds.

        Args:
            file_path: Path to the file.

        Returns:
            The file content as a string.

        Raises:
            ExtractionError: If no encoding works.
        """
        last_error: Exception | None = None

        for encoding in self.ENCODINGS:
            try:
                return file_path.read_text(encoding=encoding)
            except UnicodeDecodeError as e:
                last_error = e
                continue

        raise ExtractionError(
            f"Could not decode file with any supported encoding: {self.ENCODINGS}",
            file_path,
            cause=last_error,
        )
