"""
Unit tests for the grading engine.

Tests LLM client, prompt builder, response parser, and grading engine
with mocked LLM responses.
"""

import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from src.config import Settings, StrictnessMode
from src.grading import GradingEngine, LLMClient, LLMError, PromptBuilder, ScoringError
from src.grading.scorer import ResponseParser
from src.models import GradingResult, Rubric


class TestPromptBuilder:
    """Tests for PromptBuilder."""

    def test_get_system_prompt(self) -> None:
        """Test system prompt contains key instructions."""
        prompt = PromptBuilder.get_system_prompt()

        assert "STRICT" in prompt
        assert "NO emotions" in prompt
        assert "NO favorites" in prompt
        assert "NO leniency" in prompt
        assert "JSON" in prompt

    def test_build_grading_prompt_proportional(self, sample_rubric: Rubric) -> None:
        """Test building prompt with proportional mode."""
        answer = "Sample student answer"
        prompt = PromptBuilder.build_grading_prompt(
            sample_rubric, answer, StrictnessMode.PROPORTIONAL
        )

        assert sample_rubric.title in prompt
        assert answer in prompt
        assert "PROPORTIONAL" in prompt
        assert "partial credit" in prompt.lower()
        assert str(sample_rubric.total_max_points) in prompt

    def test_build_grading_prompt_hard_fail(self, sample_rubric: Rubric) -> None:
        """Test building prompt with hard fail mode."""
        answer = "Sample student answer"
        prompt = PromptBuilder.build_grading_prompt(sample_rubric, answer, StrictnessMode.HARD_FAIL)

        assert "HARD FAIL" in prompt
        assert "ZERO points" in prompt

    def test_build_grading_prompt_includes_all_criteria(self, sample_rubric: Rubric) -> None:
        """Test prompt includes all rubric criteria."""
        prompt = PromptBuilder.build_grading_prompt(
            sample_rubric, "answer", StrictnessMode.PROPORTIONAL
        )

        for criterion in sample_rubric.criteria:
            assert criterion.name in prompt
            assert str(criterion.max_points) in prompt


class TestResponseParser:
    """Tests for ResponseParser."""

    def test_parse_valid_response(self, sample_rubric: Rubric, sample_llm_response: str) -> None:
        """Test parsing a valid LLM response."""
        parser = ResponseParser()
        result = parser.parse(sample_llm_response, sample_rubric)

        assert isinstance(result, GradingResult)
        assert result.rubric_title == sample_rubric.title
        assert len(result.criteria_results) == len(sample_rubric.criteria)

    def test_parse_response_in_markdown_block(self, sample_rubric: Rubric) -> None:
        """Test parsing response wrapped in markdown code block."""
        json_content = {
            "total_score": 100,
            "max_possible": 100,
            "criteria_results": [
                {
                    "criterion": "Content Accuracy",
                    "max_points": 30,
                    "awarded_points": 30,
                    "justification": "Full marks",
                    "deduction_reason": None,
                },
                {
                    "criterion": "Clarity of Expression",
                    "max_points": 25,
                    "awarded_points": 25,
                    "justification": "Full marks",
                    "deduction_reason": None,
                },
                {
                    "criterion": "Supporting Evidence",
                    "max_points": 25,
                    "awarded_points": 25,
                    "justification": "Full marks",
                    "deduction_reason": None,
                },
                {
                    "criterion": "Conclusion",
                    "max_points": 20,
                    "awarded_points": 20,
                    "justification": "Full marks",
                    "deduction_reason": None,
                },
            ],
            "overall_feedback": "Perfect",
        }
        response = f"```json\n{json.dumps(json_content)}\n```"

        parser = ResponseParser()
        result = parser.parse(response, sample_rubric)

        assert result.total_awarded == Decimal("100")

    def test_parse_invalid_json(self, sample_rubric: Rubric) -> None:
        """Test parsing invalid JSON raises error."""
        parser = ResponseParser()

        with pytest.raises(ScoringError, match="No JSON object found"):
            parser.parse("this is not json", sample_rubric)

    def test_parse_missing_field(self, sample_rubric: Rubric) -> None:
        """Test parsing response with missing field raises error."""
        response = json.dumps({"total_score": 50})  # Missing other fields

        parser = ResponseParser()

        with pytest.raises(ScoringError, match="Missing required field"):
            parser.parse(response, sample_rubric)

    def test_parse_points_exceed_max(self, sample_rubric: Rubric) -> None:
        """Test parsing response where points exceed max raises error."""
        response = json.dumps(
            {
                "total_score": 150,
                "max_possible": 100,
                "criteria_results": [
                    {
                        "criterion": "Content Accuracy",
                        "max_points": 30,
                        "awarded_points": 50,  # Exceeds max!
                        "justification": "Test",
                        "deduction_reason": None,
                    }
                ],
                "overall_feedback": "Test",
            }
        )

        parser = ResponseParser()

        with pytest.raises(ScoringError, match="exceed max"):
            parser.parse(response, sample_rubric)

    def test_parse_negative_points(self, sample_rubric: Rubric) -> None:
        """Test parsing response with negative points raises error."""
        response = json.dumps(
            {
                "total_score": -10,
                "max_possible": 100,
                "criteria_results": [
                    {
                        "criterion": "Content Accuracy",
                        "max_points": 30,
                        "awarded_points": -5,  # Negative!
                        "justification": "Test",
                        "deduction_reason": None,
                    }
                ],
                "overall_feedback": "Test",
            }
        )

        parser = ResponseParser()

        with pytest.raises(ScoringError, match="Negative"):
            parser.parse(response, sample_rubric)

    def test_parse_unknown_criterion(self, sample_rubric: Rubric) -> None:
        """Test parsing response with unknown criterion raises error."""
        response = json.dumps(
            {
                "total_score": 10,
                "max_possible": 100,
                "criteria_results": [
                    {
                        "criterion": "Unknown Criterion",
                        "max_points": 10,
                        "awarded_points": 10,
                        "justification": "Test",
                        "deduction_reason": None,
                    }
                ],
                "overall_feedback": "Test",
            }
        )

        parser = ResponseParser()

        with pytest.raises(ScoringError, match="Unknown criterion"):
            parser.parse(response, sample_rubric)


class TestGradingEngine:
    """Tests for GradingEngine."""

    def test_grade_single_pass(
        self,
        sample_rubric: Rubric,
        sample_student_answer: str,
        test_settings: Settings,
        mock_llm_client: MagicMock,
    ) -> None:
        """Test grading with a single pass."""
        with patch("src.grading.engine.LLMClient", return_value=mock_llm_client):
            engine = GradingEngine(test_settings)
            result, audit = engine.grade(
                rubric=sample_rubric,
                student_answer=sample_student_answer,
                passes=1,
            )

        assert isinstance(result, GradingResult)
        assert result.llm_passes_used == 1
        assert not result.variance_detected
        mock_llm_client.generate.assert_called_once()

    def test_grade_multiple_passes(
        self,
        sample_rubric: Rubric,
        sample_student_answer: str,
        test_settings: Settings,
        sample_llm_response: str,
    ) -> None:
        """Test grading with multiple passes selects median."""
        mock_client = MagicMock()
        mock_client.generate.return_value = sample_llm_response

        with patch("src.grading.engine.LLMClient", return_value=mock_client):
            engine = GradingEngine(test_settings)
            result, audit = engine.grade(
                rubric=sample_rubric,
                student_answer=sample_student_answer,
                passes=3,
            )

        assert result.llm_passes_used == 3
        assert mock_client.generate.call_count == 3

    def test_grade_creates_audit_record(
        self,
        sample_rubric: Rubric,
        sample_student_answer: str,
        test_settings: Settings,
        mock_llm_client: MagicMock,
    ) -> None:
        """Test grading creates proper audit record."""
        with patch("src.grading.engine.LLMClient", return_value=mock_llm_client):
            engine = GradingEngine(test_settings)
            result, audit = engine.grade(
                rubric=sample_rubric,
                student_answer=sample_student_answer,
            )

        assert audit.rubric_hash is not None
        assert audit.answer_hash is not None
        assert audit.result_hash is not None
        assert audit.model_used == test_settings.zenmux_model

    def test_grade_hard_fail_mode(
        self,
        sample_rubric: Rubric,
        sample_student_answer: str,
        test_settings: Settings,
        mock_llm_client: MagicMock,
    ) -> None:
        """Test grading with hard fail strictness mode."""
        with patch("src.grading.engine.LLMClient", return_value=mock_llm_client):
            engine = GradingEngine(test_settings)
            result, audit = engine.grade(
                rubric=sample_rubric,
                student_answer=sample_student_answer,
                strictness_mode=StrictnessMode.HARD_FAIL,
            )

        # Verify prompt contained hard fail mode
        call_args = mock_llm_client.generate.call_args
        user_prompt = call_args.kwargs.get("user_prompt") or call_args[1].get("user_prompt") or call_args[0][1]
        assert "HARD FAIL" in user_prompt


class TestGradingResult:
    """Tests for GradingResult model."""

    def test_total_awarded_calculation(self, sample_grading_result: GradingResult) -> None:
        """Test total_awarded computed field."""
        expected = Decimal("28") + Decimal("25") + Decimal("22") + Decimal("20")
        assert sample_grading_result.total_awarded == expected

    def test_total_max_calculation(self, sample_grading_result: GradingResult) -> None:
        """Test total_max computed field."""
        expected = Decimal("30") + Decimal("25") + Decimal("25") + Decimal("20")
        assert sample_grading_result.total_max == expected

    def test_percentage_score_calculation(self, sample_grading_result: GradingResult) -> None:
        """Test percentage_score computed field."""
        total_awarded = Decimal("28") + Decimal("25") + Decimal("22") + Decimal("20")
        total_max = Decimal("30") + Decimal("25") + Decimal("25") + Decimal("20")
        expected = float(total_awarded / total_max * 100)

        assert abs(sample_grading_result.percentage_score - expected) < 0.01

    def test_criterion_result_percentage(self, sample_criterion_result) -> None:
        """Test CriterionResult percentage calculation."""
        expected = float(Decimal("28") / Decimal("30") * 100)
        assert abs(sample_criterion_result.percentage - expected) < 0.01
