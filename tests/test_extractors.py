"""
Unit tests for document extractors.

Tests all extractors for proper text extraction, error handling,
and edge cases like empty files and encoding issues.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.extractors import ExtractionError, create_extractor, extract_document
from src.extractors.base import DocumentExtractor
from src.extractors.docx_extractor import DocxExtractor
from src.extractors.excel_extractor import ExcelExtractor
from src.extractors.factory import get_supported_extensions
from src.extractors.pdf_extractor import PDFExtractor
from src.extractors.text_extractor import TextExtractor
from src.models import ExtractedDocument


class TestTextExtractor:
    """Tests for TextExtractor."""

    def test_extract_txt_file(self, sample_txt_file: Path) -> None:
        """Test extraction from .txt file."""
        extractor = TextExtractor()
        result = extractor.extract(sample_txt_file)

        assert isinstance(result, ExtractedDocument)
        assert "Essay Grading Rubric" in result.content
        assert result.file_extension == ".txt"
        assert result.character_count > 0

    def test_extract_md_file(self, sample_md_file: Path) -> None:
        """Test extraction from .md file."""
        extractor = TextExtractor()
        result = extractor.extract(sample_md_file)

        assert isinstance(result, ExtractedDocument)
        assert "Climate change" in result.content
        assert result.file_extension == ".md"

    def test_extract_nonexistent_file(self, temp_dir: Path) -> None:
        """Test extraction from non-existent file raises error."""
        extractor = TextExtractor()
        nonexistent = temp_dir / "nonexistent.txt"

        with pytest.raises(ExtractionError, match="does not exist"):
            extractor.extract(nonexistent)

    def test_extract_empty_file(self, empty_file: Path) -> None:
        """Test extraction from empty file raises error."""
        extractor = TextExtractor()

        with pytest.raises(ExtractionError, match="empty"):
            extractor.extract(empty_file)

    def test_extract_whitespace_only_file(self, whitespace_file: Path) -> None:
        """Test extraction from whitespace-only file raises error."""
        extractor = TextExtractor()

        with pytest.raises(ExtractionError, match="empty"):
            extractor.extract(whitespace_file)

    def test_supported_extensions(self) -> None:
        """Test that TextExtractor supports correct extensions."""
        assert TextExtractor.SUPPORTED_EXTENSIONS == (".txt", ".md")
        assert TextExtractor.supports(Path("test.txt"))
        assert TextExtractor.supports(Path("test.md"))
        assert not TextExtractor.supports(Path("test.pdf"))

    def test_extract_utf8_with_bom(self, temp_dir: Path) -> None:
        """Test extraction of UTF-8 file with BOM."""
        file_path = temp_dir / "bom.txt"
        content = "Test content with special chars: café"
        # Write with UTF-8 BOM
        file_path.write_bytes(b"\xef\xbb\xbf" + content.encode("utf-8"))

        extractor = TextExtractor()
        result = extractor.extract(file_path)

        assert "café" in result.content

    def test_extract_latin1_encoding(self, temp_dir: Path) -> None:
        """Test extraction of Latin-1 encoded file."""
        file_path = temp_dir / "latin1.txt"
        content = "Test content: résumé"
        file_path.write_bytes(content.encode("latin-1"))

        extractor = TextExtractor()
        result = extractor.extract(file_path)

        # Should successfully decode with fallback
        assert len(result.content) > 0


class TestPDFExtractor:
    """Tests for PDFExtractor."""

    def test_supported_extensions(self) -> None:
        """Test that PDFExtractor supports correct extensions."""
        assert PDFExtractor.SUPPORTED_EXTENSIONS == (".pdf",)
        assert PDFExtractor.supports(Path("test.pdf"))
        assert not PDFExtractor.supports(Path("test.txt"))

    def test_extract_nonexistent_file(self, temp_dir: Path) -> None:
        """Test extraction from non-existent file raises error."""
        extractor = PDFExtractor()
        nonexistent = temp_dir / "nonexistent.pdf"

        with pytest.raises(ExtractionError, match="does not exist"):
            extractor.extract(nonexistent)

    def test_extract_invalid_pdf(self, temp_dir: Path) -> None:
        """Test extraction from invalid PDF raises error."""
        file_path = temp_dir / "invalid.pdf"
        file_path.write_text("This is not a PDF", encoding="utf-8")

        extractor = PDFExtractor()

        with pytest.raises(ExtractionError):
            extractor.extract(file_path)


class TestDocxExtractor:
    """Tests for DocxExtractor."""

    def test_supported_extensions(self) -> None:
        """Test that DocxExtractor supports correct extensions."""
        assert DocxExtractor.SUPPORTED_EXTENSIONS == (".docx",)
        assert DocxExtractor.supports(Path("test.docx"))
        assert not DocxExtractor.supports(Path("test.doc"))  # Legacy not supported

    def test_extract_nonexistent_file(self, temp_dir: Path) -> None:
        """Test extraction from non-existent file raises error."""
        extractor = DocxExtractor()
        nonexistent = temp_dir / "nonexistent.docx"

        with pytest.raises(ExtractionError, match="does not exist"):
            extractor.extract(nonexistent)

    def test_extract_invalid_docx(self, temp_dir: Path) -> None:
        """Test extraction from invalid docx raises error."""
        file_path = temp_dir / "invalid.docx"
        file_path.write_text("This is not a DOCX", encoding="utf-8")

        extractor = DocxExtractor()

        with pytest.raises(ExtractionError):
            extractor.extract(file_path)


class TestExcelExtractor:
    """Tests for ExcelExtractor."""

    def test_supported_extensions(self) -> None:
        """Test that ExcelExtractor supports correct extensions."""
        assert ExcelExtractor.SUPPORTED_EXTENSIONS == (".xlsx", ".xls")
        assert ExcelExtractor.supports(Path("test.xlsx"))
        assert ExcelExtractor.supports(Path("test.xls"))
        assert not ExcelExtractor.supports(Path("test.csv"))

    def test_extract_nonexistent_file(self, temp_dir: Path) -> None:
        """Test extraction from non-existent file raises error."""
        extractor = ExcelExtractor()
        nonexistent = temp_dir / "nonexistent.xlsx"

        with pytest.raises(ExtractionError, match="does not exist"):
            extractor.extract(nonexistent)

    def test_extract_invalid_xlsx(self, temp_dir: Path) -> None:
        """Test extraction from invalid xlsx raises error."""
        file_path = temp_dir / "invalid.xlsx"
        file_path.write_text("This is not an Excel file", encoding="utf-8")

        extractor = ExcelExtractor()

        with pytest.raises(ExtractionError):
            extractor.extract(file_path)


class TestFactory:
    """Tests for extractor factory functions."""

    def test_get_supported_extensions(self) -> None:
        """Test that all extensions are returned."""
        extensions = get_supported_extensions()

        assert ".txt" in extensions
        assert ".md" in extensions
        assert ".pdf" in extensions
        assert ".docx" in extensions
        assert ".xlsx" in extensions
        assert ".xls" in extensions

    def test_create_extractor_txt(self) -> None:
        """Test creating extractor for txt file."""
        extractor = create_extractor(Path("test.txt"))
        assert isinstance(extractor, TextExtractor)

    def test_create_extractor_md(self) -> None:
        """Test creating extractor for md file."""
        extractor = create_extractor(Path("test.md"))
        assert isinstance(extractor, TextExtractor)

    def test_create_extractor_pdf(self) -> None:
        """Test creating extractor for pdf file."""
        extractor = create_extractor(Path("test.pdf"))
        assert isinstance(extractor, PDFExtractor)

    def test_create_extractor_docx(self) -> None:
        """Test creating extractor for docx file."""
        extractor = create_extractor(Path("test.docx"))
        assert isinstance(extractor, DocxExtractor)

    def test_create_extractor_xlsx(self) -> None:
        """Test creating extractor for xlsx file."""
        extractor = create_extractor(Path("test.xlsx"))
        assert isinstance(extractor, ExcelExtractor)

    def test_create_extractor_unsupported(self) -> None:
        """Test creating extractor for unsupported format raises error."""
        with pytest.raises(ExtractionError, match="Unsupported"):
            create_extractor(Path("test.jpg"))

    def test_extract_document_convenience(self, sample_txt_file: Path) -> None:
        """Test extract_document convenience function."""
        result = extract_document(sample_txt_file)

        assert isinstance(result, ExtractedDocument)
        assert result.content
        assert not result.is_empty


class TestExtractedDocument:
    """Tests for ExtractedDocument model."""

    def test_content_hash(self, sample_txt_file: Path) -> None:
        """Test content hash is computed correctly."""
        result = extract_document(sample_txt_file)

        # Hash should be consistent
        assert result.content_hash == result.content_hash
        assert len(result.content_hash) == 64  # SHA-256 hex length

    def test_is_empty(self, sample_txt_file: Path) -> None:
        """Test is_empty computed field."""
        result = extract_document(sample_txt_file)
        assert not result.is_empty

    def test_character_count(self, sample_txt_file: Path) -> None:
        """Test character count is computed correctly."""
        result = extract_document(sample_txt_file)
        assert result.character_count == len(result.content)
