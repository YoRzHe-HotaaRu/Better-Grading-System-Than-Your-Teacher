"""
Rubric parser module.

Parses raw text content into structured Rubric models.
Supports multiple input formats including numbered lists, markdown tables, etc.
"""

import re
from decimal import Decimal, InvalidOperation
from typing import Sequence

from src.models import Rubric, RubricCriterion


class RubricParseError(Exception):
    """Raised when rubric parsing fails."""

    def __init__(self, message: str, line_number: int | None = None):
        self.line_number = line_number
        if line_number:
            message = f"Line {line_number}: {message}"
        super().__init__(message)


class RubricParser:
    """
    Parses rubric text into structured Rubric model.

    Supports formats:
    1. Numbered list: "1. Criterion Name (10 points): Description"
    2. Markdown table: "| Criterion | Points | Description |"
    3. Simple format: "Criterion Name - 10 pts - Description"
    """

    # Patterns for different rubric formats
    NUMBERED_PATTERN = re.compile(
        r"^\s*(\d+)\.\s*"  # Number with dot
        r"([^(]+)"  # Criterion name
        r"\((\d+(?:\.\d+)?)\s*(?:points?|pts?|marks?)\)"  # Points in parentheses
        r"[:\s]*"  # Optional colon/space
        r"(.*)$",  # Description
        re.IGNORECASE,
    )

    SIMPLE_PATTERN = re.compile(
        r"^\s*"
        r"([^-]+?)"  # Criterion name
        r"\s*[-–—]\s*"  # Dash separator
        r"(\d+(?:\.\d+)?)\s*(?:points?|pts?|marks?)"  # Points
        r"\s*[-–—]\s*"  # Dash separator
        r"(.+)$",  # Description
        re.IGNORECASE,
    )

    COLON_PATTERN = re.compile(
        r"^\s*"
        r"([^:]+)"  # Criterion name
        r":\s*"  # Colon separator
        r"(\d+(?:\.\d+)?)\s*(?:points?|pts?|marks?)"  # Points
        r"[,;:\s]+"  # Separator
        r"(.+)$",  # Description
        re.IGNORECASE,
    )

    def parse(self, content: str, title: str = "Grading Rubric") -> Rubric:
        """
        Parse rubric content into a structured Rubric model.

        Args:
            content: Raw text content of the rubric.
            title: Title for the rubric.

        Returns:
            Structured Rubric object.

        Raises:
            RubricParseError: If parsing fails.
        """
        if not content or not content.strip():
            raise RubricParseError("Rubric content is empty")

        lines = content.strip().split("\n")

        # Try to detect and parse the format
        criteria = self._parse_lines(lines)

        if not criteria:
            raise RubricParseError(
                "No valid criteria found. Expected format like:\n"
                "  1. Content Accuracy (10 points): Description\n"
                "  OR: Content Accuracy - 10 pts - Description"
            )

        # Extract title from first line if it looks like a heading
        parsed_title = self._extract_title(lines) or title

        return Rubric(
            title=parsed_title,
            criteria=tuple(criteria),
        )

    def _parse_lines(self, lines: Sequence[str]) -> list[RubricCriterion]:
        """
        Parse lines and extract criteria.

        Tries multiple patterns to handle different formats.
        """
        criteria: list[RubricCriterion] = []

        for line_num, line in enumerate(lines, start=1):
            # Skip empty lines, headings, and table separators
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith("---"):
                continue
            if stripped.startswith("|") and set(stripped.replace("|", "").strip()) <= {"-", ":"}:
                continue

            # Try each pattern
            criterion = (
                self._try_numbered_format(stripped, line_num)
                or self._try_simple_format(stripped, line_num)
                or self._try_colon_format(stripped, line_num)
                or self._try_table_format(stripped, line_num)
            )

            if criterion:
                criteria.append(criterion)

        return criteria

    def _try_numbered_format(self, line: str, line_num: int) -> RubricCriterion | None:
        """Try to parse a numbered format line."""
        match = self.NUMBERED_PATTERN.match(line)
        if match:
            name = match.group(2).strip()
            points = self._parse_points(match.group(3), line_num)
            description = match.group(4).strip() or f"Evaluation of {name}"

            return RubricCriterion(
                name=name,
                max_points=points,
                description=description,
            )
        return None

    def _try_simple_format(self, line: str, line_num: int) -> RubricCriterion | None:
        """Try to parse a simple dash-separated format line."""
        match = self.SIMPLE_PATTERN.match(line)
        if match:
            name = match.group(1).strip()
            points = self._parse_points(match.group(2), line_num)
            description = match.group(3).strip()

            return RubricCriterion(
                name=name,
                max_points=points,
                description=description,
            )
        return None

    def _try_colon_format(self, line: str, line_num: int) -> RubricCriterion | None:
        """Try to parse a colon-separated format line."""
        match = self.COLON_PATTERN.match(line)
        if match:
            name = match.group(1).strip()
            points = self._parse_points(match.group(2), line_num)
            description = match.group(3).strip()

            return RubricCriterion(
                name=name,
                max_points=points,
                description=description,
            )
        return None

    def _try_table_format(self, line: str, line_num: int) -> RubricCriterion | None:
        """Try to parse a markdown table row."""
        if not line.startswith("|"):
            return None

        # Split table cells
        cells = [c.strip() for c in line.split("|")]
        cells = [c for c in cells if c]  # Remove empty cells from edges

        if len(cells) < 2:
            return None

        # Try to find points in any cell
        for i, cell in enumerate(cells):
            points_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:points?|pts?|marks?)?", cell)
            if points_match:
                points = self._parse_points(points_match.group(1), line_num)

                # Assume first cell before points is name, rest is description
                if i == 0:
                    name = cell.replace(points_match.group(0), "").strip() or f"Criterion {line_num}"
                    description = " ".join(cells[1:]) if len(cells) > 1 else f"Evaluation of {name}"
                else:
                    name = cells[0] if cells[0] else f"Criterion {line_num}"
                    description = " ".join(cells[i + 1 :]) if i + 1 < len(cells) else f"Evaluation of {name}"

                if name and points > 0:
                    return RubricCriterion(
                        name=name,
                        max_points=points,
                        description=description or f"Evaluation of {name}",
                    )
        return None

    def _parse_points(self, points_str: str, line_num: int) -> Decimal:
        """Parse points value from string."""
        try:
            points = Decimal(points_str.strip())
            if points <= 0:
                raise RubricParseError(f"Points must be positive, got {points}", line_num)
            return points
        except InvalidOperation as e:
            raise RubricParseError(f"Invalid points value: {points_str}", line_num) from e

    def _extract_title(self, lines: Sequence[str]) -> str | None:
        """Extract title from heading if present."""
        for line in lines:
            stripped = line.strip()
            # Markdown heading
            if stripped.startswith("#"):
                return stripped.lstrip("#").strip()
            # First non-empty line that doesn't look like a criterion
            if stripped and not re.search(r"\d+\s*(?:points?|pts?|marks?)", stripped, re.IGNORECASE):
                # Check if it's short enough to be a title
                if len(stripped) < 100 and not any(c in stripped for c in ["|", "-", ":"]):
                    return stripped
                break
        return None
