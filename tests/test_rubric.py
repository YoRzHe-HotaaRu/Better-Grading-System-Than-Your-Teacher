"""
Unit tests for rubric parsing and validation.

Tests rubric parser with various formats and edge cases,
and rubric validator for completeness and clarity checks.
"""

from decimal import Decimal

import pytest

from src.models import Rubric, RubricCriterion
from src.rubric import RubricParseError, RubricParser, RubricValidationError, RubricValidator


class TestRubricParser:
    """Tests for RubricParser."""

    def test_parse_numbered_format(self) -> None:
        """Test parsing numbered format rubric."""
        content = """Essay Rubric

1. Content Accuracy (30 points): Answer must be factually correct
2. Clarity (25 points): Ideas must be clearly expressed
3. Evidence (20 points): Claims must be supported with examples
"""
        parser = RubricParser()
        rubric = parser.parse(content)

        assert rubric.title == "Essay Rubric"
        assert len(rubric.criteria) == 3
        assert rubric.criteria[0].name == "Content Accuracy"
        assert rubric.criteria[0].max_points == Decimal("30")
        assert "factually correct" in rubric.criteria[0].description

    def test_parse_simple_dash_format(self) -> None:
        """Test parsing simple dash-separated format."""
        content = """
Content Accuracy - 30 pts - Answer must be factually correct
Clarity - 25 points - Ideas must be clearly expressed
"""
        parser = RubricParser()
        rubric = parser.parse(content)

        assert len(rubric.criteria) == 2
        assert rubric.criteria[0].name == "Content Accuracy"
        assert rubric.criteria[0].max_points == Decimal("30")

    def test_parse_with_decimal_points(self) -> None:
        """Test parsing rubric with decimal points."""
        content = """
1. Criterion A (10.5 points): Description A
2. Criterion B (9.5 points): Description B
"""
        parser = RubricParser()
        rubric = parser.parse(content)

        assert rubric.criteria[0].max_points == Decimal("10.5")
        assert rubric.criteria[1].max_points == Decimal("9.5")
        assert rubric.total_max_points == Decimal("20")

    def test_parse_empty_content(self) -> None:
        """Test parsing empty content raises error."""
        parser = RubricParser()

        with pytest.raises(RubricParseError, match="empty"):
            parser.parse("")

    def test_parse_whitespace_only(self) -> None:
        """Test parsing whitespace-only content raises error."""
        parser = RubricParser()

        with pytest.raises(RubricParseError, match="empty"):
            parser.parse("   \n\t\n   ")

    def test_parse_no_valid_criteria(self) -> None:
        """Test parsing content with no valid criteria raises error."""
        content = """
This is just some random text
without any valid rubric criteria
"""
        parser = RubricParser()

        with pytest.raises(RubricParseError, match="No valid criteria"):
            parser.parse(content)

    def test_parse_markdown_heading(self) -> None:
        """Test parsing rubric with markdown heading."""
        content = """# My Rubric

1. Criterion (10 points): Description here
"""
        parser = RubricParser()
        rubric = parser.parse(content)

        assert rubric.title == "My Rubric"

    def test_parse_marks_keyword(self) -> None:
        """Test parsing rubric using 'marks' instead of 'points'."""
        content = """
1. Quality (15 marks): High quality required
"""
        parser = RubricParser()
        rubric = parser.parse(content)

        assert rubric.criteria[0].max_points == Decimal("15")

    def test_parse_custom_title(self) -> None:
        """Test parsing with custom title override."""
        content = """
1. Criterion (10 points): Description
"""
        parser = RubricParser()
        rubric = parser.parse(content, title="Custom Title")

        assert rubric.title == "Custom Title"


class TestRubricValidator:
    """Tests for RubricValidator."""

    def test_validate_valid_rubric(self, sample_rubric: Rubric) -> None:
        """Test validation of a valid rubric."""
        validator = RubricValidator()
        is_valid, issues = validator.validate(sample_rubric)

        assert is_valid is True
        assert len(issues) == 0

    def test_validate_short_description(self) -> None:
        """Test validation catches short descriptions."""
        rubric = Rubric(
            title="Test Rubric",
            criteria=(
                RubricCriterion(
                    name="Criterion A",
                    description="Too short",
                    max_points=Decimal("10"),
                ),
            ),
        )

        validator = RubricValidator()
        is_valid, issues = validator.validate(rubric)

        assert is_valid is False
        assert any("too short" in issue.lower() for issue in issues)

    def test_validate_vague_description(self) -> None:
        """Test validation catches vague descriptions."""
        rubric = Rubric(
            title="Test Rubric",
            criteria=(
                RubricCriterion(
                    name="Criterion A",
                    description="The answer should be good and appropriate for the question",
                    max_points=Decimal("10"),
                ),
            ),
        )

        validator = RubricValidator()
        is_valid, issues = validator.validate(rubric)

        assert is_valid is False
        assert any("vague" in issue.lower() for issue in issues)

    def test_validate_duplicate_names(self) -> None:
        """Test validation catches duplicate criterion names."""
        with pytest.raises(ValueError, match="Duplicate"):
            Rubric(
                title="Test Rubric",
                criteria=(
                    RubricCriterion(
                        name="Same Name",
                        description="Description one that is long enough",
                        max_points=Decimal("10"),
                    ),
                    RubricCriterion(
                        name="Same Name",
                        description="Description two that is long enough",
                        max_points=Decimal("10"),
                    ),
                ),
            )

    def test_validate_excessive_points(self) -> None:
        """Test validation warns about excessive points."""
        rubric = Rubric(
            title="Test Rubric",
            criteria=(
                RubricCriterion(
                    name="Criterion A",
                    description="This is a sufficiently long description for testing",
                    max_points=Decimal("500"),
                ),
                RubricCriterion(
                    name="Criterion B",
                    description="This is also a sufficiently long description for testing",
                    max_points=Decimal("600"),
                ),
            ),
        )

        validator = RubricValidator()
        is_valid, issues = validator.validate(rubric)

        # Should have a warning about high total
        assert any("unusually high" in issue.lower() for issue in issues)

    def test_validate_or_raise_valid(self, sample_rubric: Rubric) -> None:
        """Test validate_or_raise doesn't raise for valid rubric."""
        validator = RubricValidator()
        validator.validate_or_raise(sample_rubric)  # Should not raise

    def test_validate_or_raise_invalid(self) -> None:
        """Test validate_or_raise raises for invalid rubric."""
        rubric = Rubric(
            title="Test Rubric",
            criteria=(
                RubricCriterion(
                    name="A",
                    description="short",
                    max_points=Decimal("10"),
                ),
            ),
        )

        validator = RubricValidator()

        with pytest.raises(RubricValidationError):
            validator.validate_or_raise(rubric)


class TestRubricModel:
    """Tests for Rubric and RubricCriterion models."""

    def test_rubric_total_points(self, sample_rubric: Rubric) -> None:
        """Test total_max_points computed field."""
        expected_total = Decimal("30") + Decimal("25") + Decimal("25") + Decimal("20")
        assert sample_rubric.total_max_points == expected_total

    def test_rubric_criterion_count(self, sample_rubric: Rubric) -> None:
        """Test criterion_count computed field."""
        assert sample_rubric.criterion_count == 4

    def test_criterion_immutable(self, sample_criterion: RubricCriterion) -> None:
        """Test that criteria are immutable."""
        with pytest.raises(Exception):  # Pydantic frozen model
            sample_criterion.name = "New Name"  # type: ignore

    def test_rubric_immutable(self, sample_rubric: Rubric) -> None:
        """Test that rubric is immutable."""
        with pytest.raises(Exception):  # Pydantic frozen model
            sample_rubric.title = "New Title"  # type: ignore

    def test_criterion_requires_positive_points(self) -> None:
        """Test that criterion requires positive points."""
        with pytest.raises(ValueError):
            RubricCriterion(
                name="Test",
                description="Description",
                max_points=Decimal("0"),
            )

    def test_criterion_requires_nonempty_name(self) -> None:
        """Test that criterion requires non-empty name."""
        with pytest.raises(ValueError):
            RubricCriterion(
                name="",
                description="Description",
                max_points=Decimal("10"),
            )

    def test_rubric_requires_at_least_one_criterion(self) -> None:
        """Test that rubric requires at least one criterion."""
        with pytest.raises(ValueError):
            Rubric(title="Test", criteria=())
