"""
PDF document extractor using PyMuPDF.

PyMuPDF (fitz) is the fastest and most accurate PDF text extraction
library available for Python, with excellent layout preservation.
"""

from pathlib import Path
from typing import ClassVar

import fitz  # PyMuPDF

from src.extractors.base import DocumentExtractor, ExtractionError
from src.models import ExtractedDocument


class PDFExtractor(DocumentExtractor):
    """
    Extracts text content from PDF files.

    Uses PyMuPDF for fast, accurate extraction with layout preservation.
    Handles multi-page documents and maintains reading order.
    """

    SUPPORTED_EXTENSIONS: ClassVar[tuple[str, ...]] = (".pdf",)

    def extract(self, file_path: Path) -> ExtractedDocument:
        """
        Extract text from a PDF file.

        Args:
            file_path: Path to the PDF file.

        Returns:
            ExtractedDocument with the extracted text.

        Raises:
            ExtractionError: If the PDF cannot be read or is corrupted.
        """
        self._validate_file(file_path)

        try:
            text_parts: list[str] = []

            # Open PDF with PyMuPDF
            with fitz.open(file_path) as doc:
                if doc.page_count == 0:
                    raise ExtractionError("PDF has no pages", file_path)

                for page_num, page in enumerate(doc, start=1):
                    # Extract text with layout preservation
                    page_text = page.get_text(
                        "text",
                        flags=fitz.TEXT_PRESERVE_WHITESPACE | fitz.TEXT_PRESERVE_LIGATURES,
                    )

                    if page_text.strip():
                        text_parts.append(f"--- Page {page_num} ---\n{page_text}")

            if not text_parts:
                # PDF might be image-only (scanned)
                raise ExtractionError(
                    "No text could be extracted. The PDF may be image-based (scanned). "
                    "OCR is not currently supported.",
                    file_path,
                )

            full_text = "\n\n".join(text_parts)
            return self._create_result(full_text, file_path)

        except fitz.FileDataError as e:
            raise ExtractionError("PDF file is corrupted or invalid", file_path, cause=e) from e
        except fitz.EmptyFileError as e:
            raise ExtractionError("PDF file is empty", file_path, cause=e) from e
        except ExtractionError:
            raise
        except Exception as e:
            raise ExtractionError(f"Unexpected error: {e}", file_path, cause=e) from e
