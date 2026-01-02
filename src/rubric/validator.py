"""
Rubric validation module.

Provides strict validation of rubrics to ensure they are complete,
unambiguous, and suitable for consistent grading.
"""

from decimal import Decimal
from typing import Sequence

from src.models import Rubric, RubricCriterion


class RubricValidationError(Exception):
    """Raised when rubric validation fails."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        message = "Rubric validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        super().__init__(message)


class RubricValidator:
    """
    Validates rubrics for completeness and consistency.

    Checks:
    1. All criteria have clear descriptions
    2. Points are reasonable and sum to a valid total
    3. No overlapping or duplicate criteria
    4. Descriptions are specific enough for consistent grading
    """

    # Minimum description length for clarity
    MIN_DESCRIPTION_LENGTH = 10

    # Maximum allowed points per criterion (sanity check)
    MAX_POINTS_PER_CRITERION = Decimal("1000")

    # Words that indicate vague descriptions
    VAGUE_WORDS = frozenset(
        [
            "good",
            "bad",
            "nice",
            "okay",
            "fine",
            "appropriate",
            "adequate",
            "sufficient",
            "reasonable",
        ]
    )

    def validate(self, rubric: Rubric) -> tuple[bool, list[str]]:
        """
        Validate a rubric and return any issues found.

        Args:
            rubric: The rubric to validate.

        Returns:
            Tuple of (is_valid, list of issues).
        """
        issues: list[str] = []

        # Check basic structure
        issues.extend(self._validate_structure(rubric))

        # Check each criterion
        for i, criterion in enumerate(rubric.criteria, start=1):
            issues.extend(self._validate_criterion(criterion, i))

        # Check for duplicates
        issues.extend(self._check_duplicates(rubric.criteria))

        # Check total points sanity
        issues.extend(self._validate_total_points(rubric))

        return len(issues) == 0, issues

    def validate_or_raise(self, rubric: Rubric) -> None:
        """
        Validate a rubric and raise if invalid.

        Args:
            rubric: The rubric to validate.

        Raises:
            RubricValidationError: If validation fails.
        """
        is_valid, issues = self.validate(rubric)
        if not is_valid:
            raise RubricValidationError(issues)

    def _validate_structure(self, rubric: Rubric) -> list[str]:
        """Validate basic rubric structure."""
        issues: list[str] = []

        if not rubric.title.strip():
            issues.append("Rubric title is empty")

        if not rubric.criteria:
            issues.append("Rubric has no criteria")

        return issues

    def _validate_criterion(self, criterion: RubricCriterion, index: int) -> list[str]:
        """Validate a single criterion."""
        issues: list[str] = []
        prefix = f"Criterion {index} ({criterion.name})"

        # Check name
        if len(criterion.name.strip()) < 2:
            issues.append(f"{prefix}: Name is too short")

        # Check description length
        if len(criterion.description.strip()) < self.MIN_DESCRIPTION_LENGTH:
            issues.append(
                f"{prefix}: Description is too short (minimum {self.MIN_DESCRIPTION_LENGTH} characters). "
                "Clear descriptions are essential for consistent grading."
            )

        # Check for vague descriptions
        description_lower = criterion.description.lower()
        vague_found = [w for w in self.VAGUE_WORDS if w in description_lower]
        if vague_found:
            issues.append(
                f"{prefix}: Description contains vague words ({', '.join(vague_found)}). "
                "Use specific, measurable criteria instead."
            )

        # Check points range
        if criterion.max_points > self.MAX_POINTS_PER_CRITERION:
            issues.append(
                f"{prefix}: Points ({criterion.max_points}) exceed maximum "
                f"allowed ({self.MAX_POINTS_PER_CRITERION})"
            )

        return issues

    def _check_duplicates(self, criteria: Sequence[RubricCriterion]) -> list[str]:
        """Check for duplicate criterion names."""
        issues: list[str] = []
        seen_names: dict[str, int] = {}

        for i, criterion in enumerate(criteria, start=1):
            name_lower = criterion.name.lower().strip()
            if name_lower in seen_names:
                issues.append(
                    f"Duplicate criterion name: '{criterion.name}' "
                    f"(appears at positions {seen_names[name_lower]} and {i})"
                )
            else:
                seen_names[name_lower] = i

        return issues

    def _validate_total_points(self, rubric: Rubric) -> list[str]:
        """Validate total points are sensible."""
        issues: list[str] = []

        if rubric.total_max_points <= 0:
            issues.append("Total points must be greater than 0")

        # Warn if total seems unusual (but don't fail)
        if rubric.total_max_points > Decimal("1000"):
            issues.append(
                f"Total points ({rubric.total_max_points}) is unusually high. "
                "Consider if this is intentional."
            )

        return issues
