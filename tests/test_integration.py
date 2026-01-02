"""
Integration tests for the full grading pipeline.

Tests end-to-end grading scenarios with mocked LLM responses
to verify the complete system works correctly.
"""

import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.config import Settings, StrictnessMode
from src.extractors import extract_document
from src.grading import GradingEngine
from src.output import AuditTrail, ReportFormat, ReportGenerator
from src.rubric import RubricParser, RubricValidator


class TestFullPipeline:
    """Integration tests for the complete grading pipeline."""

    def test_full_grading_pipeline(
        self,
        sample_txt_file: Path,
        sample_md_file: Path,
        sample_llm_response: str,
        test_settings: Settings,
    ) -> None:
        """Test complete pipeline from files to grading result."""
        # Step 1: Extract documents
        rubric_doc = extract_document(sample_txt_file)
        answer_doc = extract_document(sample_md_file)

        assert rubric_doc.content
        assert answer_doc.content

        # Step 2: Parse rubric
        parser = RubricParser()
        rubric = parser.parse(rubric_doc.content)

        assert rubric.criterion_count == 4
        assert rubric.total_max_points == Decimal("100")

        # Step 3: Validate rubric
        validator = RubricValidator()
        is_valid, issues = validator.validate(rubric)

        assert is_valid

        # Step 4: Grade with mocked LLM
        mock_client = MagicMock()
        mock_client.generate.return_value = sample_llm_response

        with patch("src.grading.engine.LLMClient", return_value=mock_client):
            engine = GradingEngine(test_settings)
            result, audit = engine.grade(
                rubric=rubric,
                student_answer=answer_doc.content,
            )

        assert result.rubric_title == rubric.title
        assert len(result.criteria_results) == 4
        assert result.total_awarded > 0
        assert result.percentage_score > 0

    def test_report_generation_json(
        self,
        sample_grading_result,
        temp_dir: Path,
    ) -> None:
        """Test JSON report generation."""
        generator = ReportGenerator()
        output_path = temp_dir / "report.json"

        saved_path = generator.save(sample_grading_result, output_path)

        assert saved_path.exists()

        # Verify JSON is valid
        content = json.loads(saved_path.read_text(encoding="utf-8"))
        assert "grading_result" in content
        assert content["grading_result"]["total_awarded"] == float(
            sample_grading_result.total_awarded
        )

    def test_report_generation_csv(
        self,
        sample_grading_result,
        temp_dir: Path,
    ) -> None:
        """Test CSV report generation."""
        generator = ReportGenerator()
        output_path = temp_dir / "report.csv"

        saved_path = generator.save(sample_grading_result, output_path)

        assert saved_path.exists()

        content = saved_path.read_text(encoding="utf-8")
        assert "Criterion" in content
        assert "Max Points" in content
        assert "TOTAL" in content

    def test_report_generation_markdown(
        self,
        sample_grading_result,
        temp_dir: Path,
    ) -> None:
        """Test Markdown report generation."""
        generator = ReportGenerator()
        output_path = temp_dir / "report.md"

        saved_path = generator.save(sample_grading_result, output_path)

        assert saved_path.exists()

        content = saved_path.read_text(encoding="utf-8")
        assert "# Grading Report" in content
        assert "## Summary" in content
        assert "## Criteria Breakdown" in content

    def test_audit_trail_save_and_load(
        self,
        sample_txt_file: Path,
        sample_md_file: Path,
        sample_llm_response: str,
        test_settings: Settings,
        temp_dir: Path,
    ) -> None:
        """Test audit trail persistence."""
        # Generate a grading result
        rubric_doc = extract_document(sample_txt_file)
        answer_doc = extract_document(sample_md_file)
        parser = RubricParser()
        rubric = parser.parse(rubric_doc.content)

        mock_client = MagicMock()
        mock_client.generate.return_value = sample_llm_response

        with patch("src.grading.engine.LLMClient", return_value=mock_client):
            engine = GradingEngine(test_settings)
            result, audit = engine.grade(rubric=rubric, student_answer=answer_doc.content)

        # Save audit
        audit_trail = AuditTrail(temp_dir / "audits")
        saved_path = audit_trail.save(audit)

        assert saved_path.exists()

        # Load audit
        loaded = audit_trail.load(audit.audit_id)

        assert loaded is not None
        assert loaded.audit_id == audit.audit_id
        assert loaded.rubric_hash == audit.rubric_hash
        assert loaded.answer_hash == audit.answer_hash

    def test_audit_verification(
        self,
        sample_txt_file: Path,
        sample_md_file: Path,
        sample_llm_response: str,
        test_settings: Settings,
        temp_dir: Path,
    ) -> None:
        """Test audit verification with matching and non-matching content."""
        rubric_doc = extract_document(sample_txt_file)
        answer_doc = extract_document(sample_md_file)
        parser = RubricParser()
        rubric = parser.parse(rubric_doc.content)

        mock_client = MagicMock()
        mock_client.generate.return_value = sample_llm_response

        with patch("src.grading.engine.LLMClient", return_value=mock_client):
            engine = GradingEngine(test_settings)
            result, audit = engine.grade(rubric=rubric, student_answer=answer_doc.content)

        audit_trail = AuditTrail(temp_dir / "audits")

        # Verification should pass with same content
        # We need to create the same hash format as the engine
        rubric_content = f"{rubric.title}\n" + "\n".join(
            f"{c.name}: {c.max_points} - {c.description}" for c in rubric.criteria
        )

        assert audit_trail.verify(audit, rubric_content, answer_doc.content)

        # Verification should fail with different content
        assert not audit_trail.verify(audit, "different rubric", answer_doc.content)
        assert not audit_trail.verify(audit, rubric_content, "different answer")


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_rubric_with_single_criterion(
        self,
        sample_student_answer: str,
        sample_llm_response: str,
        test_settings: Settings,
    ) -> None:
        """Test grading with a single criterion rubric."""
        rubric_text = """Simple Rubric
1. Only Criterion (100 points): The answer must be complete
"""
        parser = RubricParser()
        rubric = parser.parse(rubric_text)

        assert rubric.criterion_count == 1

        # Create matching LLM response
        response = json.dumps({
            "total_score": 80,
            "max_possible": 100,
            "criteria_results": [
                {
                    "criterion": "Only Criterion",
                    "max_points": 100,
                    "awarded_points": 80,
                    "justification": "Good answer",
                    "deduction_reason": "Minor issues",
                }
            ],
            "overall_feedback": "Good work",
        })

        mock_client = MagicMock()
        mock_client.generate.return_value = response

        with patch("src.grading.engine.LLMClient", return_value=mock_client):
            engine = GradingEngine(test_settings)
            result, audit = engine.grade(
                rubric=rubric,
                student_answer=sample_student_answer,
            )

        assert result.total_awarded == Decimal("80")
        assert result.percentage_score == 80.0

    def test_perfect_score(
        self,
        sample_rubric,
        sample_student_answer: str,
        test_settings: Settings,
    ) -> None:
        """Test handling of perfect score."""
        response = json.dumps({
            "total_score": 100,
            "max_possible": 100,
            "criteria_results": [
                {
                    "criterion": "Content Accuracy",
                    "max_points": 30,
                    "awarded_points": 30,
                    "justification": "Perfect",
                    "deduction_reason": None,
                },
                {
                    "criterion": "Clarity of Expression",
                    "max_points": 25,
                    "awarded_points": 25,
                    "justification": "Perfect",
                    "deduction_reason": None,
                },
                {
                    "criterion": "Supporting Evidence",
                    "max_points": 25,
                    "awarded_points": 25,
                    "justification": "Perfect",
                    "deduction_reason": None,
                },
                {
                    "criterion": "Conclusion",
                    "max_points": 20,
                    "awarded_points": 20,
                    "justification": "Perfect",
                    "deduction_reason": None,
                },
            ],
            "overall_feedback": "Excellent work!",
        })

        mock_client = MagicMock()
        mock_client.generate.return_value = response

        with patch("src.grading.engine.LLMClient", return_value=mock_client):
            engine = GradingEngine(test_settings)
            result, audit = engine.grade(
                rubric=sample_rubric,
                student_answer=sample_student_answer,
            )

        assert result.total_awarded == result.total_max
        assert result.percentage_score == 100.0

    def test_zero_score(
        self,
        sample_rubric,
        sample_student_answer: str,
        test_settings: Settings,
    ) -> None:
        """Test handling of zero score."""
        response = json.dumps({
            "total_score": 0,
            "max_possible": 100,
            "criteria_results": [
                {
                    "criterion": "Content Accuracy",
                    "max_points": 30,
                    "awarded_points": 0,
                    "justification": "Completely incorrect",
                    "deduction_reason": "Failed all requirements",
                },
                {
                    "criterion": "Clarity of Expression",
                    "max_points": 25,
                    "awarded_points": 0,
                    "justification": "Unintelligible",
                    "deduction_reason": "No clear expression",
                },
                {
                    "criterion": "Supporting Evidence",
                    "max_points": 25,
                    "awarded_points": 0,
                    "justification": "No evidence provided",
                    "deduction_reason": "Missing evidence",
                },
                {
                    "criterion": "Conclusion",
                    "max_points": 20,
                    "awarded_points": 0,
                    "justification": "No conclusion",
                    "deduction_reason": "Missing conclusion",
                },
            ],
            "overall_feedback": "Needs significant improvement.",
        })

        mock_client = MagicMock()
        mock_client.generate.return_value = response

        with patch("src.grading.engine.LLMClient", return_value=mock_client):
            engine = GradingEngine(test_settings)
            result, audit = engine.grade(
                rubric=sample_rubric,
                student_answer=sample_student_answer,
            )

        assert result.total_awarded == Decimal("0")
        assert result.percentage_score == 0.0
