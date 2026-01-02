"""
Response parser and scorer for LLM grading output.

Parses the JSON response from the LLM and validates it against
the rubric constraints. Ensures scores are within bounds and
all criteria are accounted for.
"""

import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from src.models import CriterionResult, GradingResult, Rubric


class ScoringError(Exception):
    """Raised when score parsing or validation fails."""

    def __init__(self, message: str, raw_response: str | None = None):
        self.raw_response = raw_response
        super().__init__(message)


class ResponseParser:
    """
    Parses and validates LLM grading responses.

    Ensures:
    1. Response is valid JSON
    2. All expected fields are present
    3. Scores are within valid ranges
    4. All rubric criteria are accounted for
    """

    def parse(self, response: str, rubric: Rubric) -> GradingResult:
        """
        Parse an LLM response into a GradingResult.

        Args:
            response: Raw LLM response (expected JSON).
            rubric: The rubric used for grading.

        Returns:
            Validated GradingResult.

        Raises:
            ScoringError: If parsing or validation fails.
        """
        # Extract JSON from response (handle markdown code blocks)
        json_str = self._extract_json(response)

        # Parse JSON
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ScoringError(
                f"Invalid JSON in response: {e}",
                raw_response=response,
            ) from e

        # Validate and convert to GradingResult
        return self._validate_and_convert(data, rubric, response)

    def _extract_json(self, response: str) -> str:
        """
        Extract JSON from response, handling common formats.

        Args:
            response: Raw response text.

        Returns:
            Extracted JSON string.
        """
        # Remove markdown code block if present
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", response)
        if json_match:
            return json_match.group(1).strip()

        # Try to find JSON object directly
        # Look for the outermost { }
        brace_start = response.find("{")
        if brace_start == -1:
            raise ScoringError("No JSON object found in response", raw_response=response)

        # Find matching closing brace
        depth = 0
        for i, char in enumerate(response[brace_start:], start=brace_start):
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return response[brace_start : i + 1]

        raise ScoringError("Unclosed JSON object in response", raw_response=response)

    def _validate_and_convert(
        self, data: dict[str, Any], rubric: Rubric, raw_response: str
    ) -> GradingResult:
        """
        Validate parsed data and convert to GradingResult.

        Args:
            data: Parsed JSON data.
            rubric: The rubric used for grading.
            raw_response: Original response for error reporting.

        Returns:
            Validated GradingResult.


        Raises:
            ScoringError: If validation fails.
        """
        # Check required fields
        required_fields = ["total_score", "max_possible", "criteria_results", "overall_feedback"]
        for field in required_fields:
            if field not in data:
                raise ScoringError(f"Missing required field: {field}", raw_response=raw_response)

        # Validate and convert criteria results
        criteria_results = self._parse_criteria_results(
            data["criteria_results"], rubric, raw_response
        )

        # Validate total score
        reported_total = self._parse_decimal(data["total_score"], "total_score", raw_response)
        calculated_total = sum(r.awarded_points for r in criteria_results)

        # Allow small floating point differences
        if abs(reported_total - calculated_total) > Decimal("0.01"):
            # Use calculated total as it's more reliable
            pass  # We'll use calculated total in the result

        # Validate max possible matches rubric
        reported_max = self._parse_decimal(data["max_possible"], "max_possible", raw_response)
        if reported_max != rubric.total_max_points:
            raise ScoringError(
                f"max_possible ({reported_max}) doesn't match rubric total ({rubric.total_max_points})",
                raw_response=raw_response,
            )

        # Create result
        return GradingResult(
            rubric_title=rubric.title,
            criteria_results=tuple(criteria_results),
            overall_feedback=str(data["overall_feedback"]),
        )

    def _parse_criteria_results(
        self, results_data: list[dict[str, Any]], rubric: Rubric, raw_response: str
    ) -> list[CriterionResult]:
        """
        Parse and validate criterion results.

        Args:
            results_data: List of criterion result dicts from LLM.
            rubric: The rubric for validation.
            raw_response: Original response for error reporting.

        Returns:
            List of validated CriterionResult objects.

        Raises:
            ScoringError: If validation fails.
        """
        if not isinstance(results_data, list):
            raise ScoringError("criteria_results must be a list", raw_response=raw_response)

        # Build lookup of rubric criteria
        rubric_lookup = {c.name.lower(): c for c in rubric.criteria}

        results: list[CriterionResult] = []
        seen_criteria: set[str] = set()

        for i, item in enumerate(results_data):
            if not isinstance(item, dict):
                raise ScoringError(
                    f"criteria_results[{i}] must be an object", raw_response=raw_response
                )

            # Get criterion name
            criterion_name = str(item.get("criterion", ""))
            if not criterion_name:
                raise ScoringError(
                    f"criteria_results[{i}] missing criterion name", raw_response=raw_response
                )

            # Find matching rubric criterion
            rubric_criterion = rubric_lookup.get(criterion_name.lower())
            if not rubric_criterion:
                # Try partial match
                for name, crit in rubric_lookup.items():
                    if name in criterion_name.lower() or criterion_name.lower() in name:
                        rubric_criterion = crit
                        break

            if not rubric_criterion:
                raise ScoringError(
                    f"Unknown criterion: '{criterion_name}'", raw_response=raw_response
                )

            # Check for duplicates
            if rubric_criterion.name.lower() in seen_criteria:
                raise ScoringError(
                    f"Duplicate criterion in response: '{criterion_name}'",
                    raw_response=raw_response,
                )
            seen_criteria.add(rubric_criterion.name.lower())

            # Parse points
            max_points = rubric_criterion.max_points
            awarded_points = self._parse_decimal(
                item.get("awarded_points", 0), f"criteria_results[{i}].awarded_points", raw_response
            )

            # Validate points range
            if awarded_points < 0:
                raise ScoringError(
                    f"Negative points for '{criterion_name}': {awarded_points}",
                    raw_response=raw_response,
                )
            if awarded_points > max_points:
                raise ScoringError(
                    f"Points for '{criterion_name}' ({awarded_points}) exceed max ({max_points})",
                    raw_response=raw_response,
                )

            # Get justification and deduction reason
            justification = str(item.get("justification", ""))
            if not justification:
                raise ScoringError(
                    f"Missing justification for '{criterion_name}'", raw_response=raw_response
                )

            deduction_reason = item.get("deduction_reason")
            if deduction_reason is not None and not isinstance(deduction_reason, str):
                deduction_reason = str(deduction_reason)
            if deduction_reason == "null":
                deduction_reason = None

            results.append(
                CriterionResult(
                    criterion_name=rubric_criterion.name,
                    max_points=max_points,
                    awarded_points=awarded_points,
                    justification=justification,
                    deduction_reason=deduction_reason,
                )
            )

        # Check all criteria are accounted for
        missing = set(rubric_lookup.keys()) - seen_criteria
        if missing:
            missing_names = [rubric_lookup[m].name for m in missing]
            raise ScoringError(
                f"Missing criteria in response: {missing_names}", raw_response=raw_response
            )

        return results

    def _parse_decimal(self, value: Any, field_name: str, raw_response: str) -> Decimal:
        """
        Parse a value as Decimal.

        Args:
            value: Value to parse.
            field_name: Field name for error messages.
            raw_response: Original response for error reporting.

        Returns:
            Decimal value.

        Raises:
            ScoringError: If parsing fails.
        """
        try:
            if isinstance(value, Decimal):
                return value
            return Decimal(str(value))
        except (InvalidOperation, ValueError) as e:
            raise ScoringError(
                f"Invalid numeric value for {field_name}: {value}", raw_response=raw_response
            ) from e
