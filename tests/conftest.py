"""
Pytest configuration and fixtures.

Provides common test fixtures for all test modules.
"""

import json
import os
import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Any, Generator
from unittest.mock import MagicMock, patch

import pytest

from src.config import Settings, StrictnessMode
from src.models import (
    AuditRecord,
    CriterionResult,
    ExtractedDocument,
    GradingResult,
    Rubric,
    RubricCriterion,
)


# ==============================================================================
# Directory Fixtures
# ==============================================================================


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the path to the test fixtures directory."""
    return Path(__file__).parent / "fixtures"


# ==============================================================================
# Sample Rubric Fixtures
# ==============================================================================


@pytest.fixture
def sample_criterion() -> RubricCriterion:
    """Create a sample rubric criterion."""
    return RubricCriterion(
        name="Content Accuracy",
        description="The answer must accurately address the question with correct facts",
        max_points=Decimal("10"),
        allows_partial_credit=True,
    )


@pytest.fixture
def sample_rubric() -> Rubric:
    """Create a sample rubric with multiple criteria."""
    return Rubric(
        title="Essay Grading Rubric",
        description="Standard essay evaluation rubric",
        criteria=(
            RubricCriterion(
                name="Content Accuracy",
                description="The answer demonstrates accurate understanding of the topic with correct facts",
                max_points=Decimal("30"),
            ),
            RubricCriterion(
                name="Clarity of Expression",
                description="Ideas are expressed clearly and coherently with logical flow",
                max_points=Decimal("25"),
            ),
            RubricCriterion(
                name="Supporting Evidence",
                description="Claims are supported with relevant examples and evidence",
                max_points=Decimal("25"),
            ),
            RubricCriterion(
                name="Conclusion",
                description="Essay includes a strong conclusion that summarizes key points",
                max_points=Decimal("20"),
            ),
        ),
    )


@pytest.fixture
def sample_rubric_text() -> str:
    """Sample rubric in text format."""
    return """Essay Grading Rubric

1. Content Accuracy (30 points): The answer demonstrates accurate understanding of the topic with correct facts
2. Clarity of Expression (25 points): Ideas are expressed clearly and coherently with logical flow
3. Supporting Evidence (25 points): Claims are supported with relevant examples and evidence
4. Conclusion (20 points): Essay includes a strong conclusion that summarizes key points
"""


# ==============================================================================
# Sample Answer Fixtures
# ==============================================================================


@pytest.fixture
def sample_student_answer() -> str:
    """Sample student answer text."""
    return """
Climate change is one of the most pressing issues facing our planet today. 
The Earth's average temperature has risen by approximately 1.1 degrees Celsius 
since the pre-industrial era, primarily due to human activities such as burning 
fossil fuels and deforestation.

The effects of climate change are far-reaching. Rising sea levels threaten 
coastal communities, extreme weather events are becoming more frequent, and 
ecosystems are being disrupted. According to the IPCC, we must reduce greenhouse 
gas emissions by 45% by 2030 to limit warming to 1.5 degrees.

To address this crisis, governments and individuals must take action. This includes 
transitioning to renewable energy sources, improving energy efficiency, and 
protecting forests. The Paris Agreement represents a global commitment to these goals.

In conclusion, climate change requires immediate attention. By working together 
and implementing sustainable practices, we can mitigate its worst effects and 
protect our planet for future generations.
"""


# ==============================================================================
# Grading Result Fixtures
# ==============================================================================


@pytest.fixture
def sample_criterion_result() -> CriterionResult:
    """Sample criterion grading result."""
    return CriterionResult(
        criterion_name="Content Accuracy",
        max_points=Decimal("30"),
        awarded_points=Decimal("28"),
        justification="The answer accurately describes climate change causes and effects, citing the 1.1C temperature rise and IPCC data.",
        deduction_reason="Minor deduction: Could have mentioned more specific scientific data sources.",
    )


@pytest.fixture
def sample_grading_result(sample_rubric: Rubric) -> GradingResult:
    """Sample complete grading result."""
    return GradingResult(
        rubric_title=sample_rubric.title,
        criteria_results=(
            CriterionResult(
                criterion_name="Content Accuracy",
                max_points=Decimal("30"),
                awarded_points=Decimal("28"),
                justification="Accurate facts about climate change including temperature data.",
                deduction_reason="Could cite more scientific sources.",
            ),
            CriterionResult(
                criterion_name="Clarity of Expression",
                max_points=Decimal("25"),
                awarded_points=Decimal("25"),
                justification="Clear and logical flow throughout the essay.",
                deduction_reason=None,
            ),
            CriterionResult(
                criterion_name="Supporting Evidence",
                max_points=Decimal("25"),
                awarded_points=Decimal("22"),
                justification="Good use of IPCC data and Paris Agreement reference.",
                deduction_reason="More diverse evidence sources would strengthen the argument.",
            ),
            CriterionResult(
                criterion_name="Conclusion",
                max_points=Decimal("20"),
                awarded_points=Decimal("20"),
                justification="Strong conclusion that summarizes key points effectively.",
                deduction_reason=None,
            ),
        ),
        overall_feedback="Well-structured essay with accurate content. Consider adding more diverse evidence sources for a stronger argument.",
    )


# ==============================================================================
# LLM Response Fixtures
# ==============================================================================


@pytest.fixture
def sample_llm_response() -> str:
    """Sample LLM grading response in JSON format."""
    return json.dumps(
        {
            "total_score": 95,
            "max_possible": 100,
            "criteria_results": [
                {
                    "criterion": "Content Accuracy",
                    "max_points": 30,
                    "awarded_points": 28,
                    "justification": "Accurate facts about climate change including temperature data.",
                    "deduction_reason": "Could cite more scientific sources.",
                },
                {
                    "criterion": "Clarity of Expression",
                    "max_points": 25,
                    "awarded_points": 25,
                    "justification": "Clear and logical flow throughout the essay.",
                    "deduction_reason": None,
                },
                {
                    "criterion": "Supporting Evidence",
                    "max_points": 25,
                    "awarded_points": 22,
                    "justification": "Good use of IPCC data and Paris Agreement reference.",
                    "deduction_reason": "More diverse evidence sources would strengthen the argument.",
                },
                {
                    "criterion": "Conclusion",
                    "max_points": 20,
                    "awarded_points": 20,
                    "justification": "Strong conclusion that summarizes key points effectively.",
                    "deduction_reason": None,
                },
            ],
            "overall_feedback": "Well-structured essay with accurate content.",
        }
    )


# ==============================================================================
# Settings Fixtures
# ==============================================================================


@pytest.fixture
def test_settings(temp_dir: Path) -> Settings:
    """Create test settings with mocked values."""
    return Settings(
        zenmux_api_key="test-api-key-for-testing",
        zenmux_base_url="https://test.api.local",
        zenmux_model="test-model",
        grading_passes=1,
        llm_temperature=0.0,
        max_variance_percent=5.0,
        strictness_mode=StrictnessMode.PROPORTIONAL,
        output_directory=temp_dir / "output",
    )


# ==============================================================================
# Mock Fixtures
# ==============================================================================


@pytest.fixture
def mock_llm_client(sample_llm_response: str) -> Generator[MagicMock, None, None]:
    """Mock the LLM client to avoid actual API calls."""
    with patch("src.grading.engine.LLMClient") as mock_class:
        mock_instance = MagicMock()
        mock_instance.generate.return_value = sample_llm_response
        mock_instance.health_check.return_value = True
        mock_class.return_value = mock_instance
        yield mock_instance


# ==============================================================================
# File Fixtures
# ==============================================================================


@pytest.fixture
def sample_txt_file(temp_dir: Path, sample_rubric_text: str) -> Path:
    """Create a sample text file."""
    file_path = temp_dir / "rubric.txt"
    file_path.write_text(sample_rubric_text, encoding="utf-8")
    return file_path


@pytest.fixture
def sample_md_file(temp_dir: Path, sample_student_answer: str) -> Path:
    """Create a sample markdown file."""
    file_path = temp_dir / "answer.md"
    file_path.write_text(sample_student_answer, encoding="utf-8")
    return file_path


@pytest.fixture
def empty_file(temp_dir: Path) -> Path:
    """Create an empty file."""
    file_path = temp_dir / "empty.txt"
    file_path.write_text("", encoding="utf-8")
    return file_path


@pytest.fixture
def whitespace_file(temp_dir: Path) -> Path:
    """Create a file with only whitespace."""
    file_path = temp_dir / "whitespace.txt"
    file_path.write_text("   \n\t\n   ", encoding="utf-8")
    return file_path
