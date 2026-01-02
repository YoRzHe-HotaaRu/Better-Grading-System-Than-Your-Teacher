"""
Grading engine - the core orchestrator.

Implements multi-pass grading for consistency, variance detection,
and audit trail generation.
"""

import statistics
from datetime import datetime
from decimal import Decimal
from typing import NamedTuple

from src.config import Settings, StrictnessMode, get_settings
from src.grading.llm_client import LLMClient, LLMError
from src.grading.prompt_builder import PromptBuilder
from src.grading.scorer import ResponseParser, ScoringError
from src.models import AuditRecord, CriterionResult, GradingResult, Rubric


class GradingPass(NamedTuple):
    """Result of a single grading pass."""

    result: GradingResult
    raw_response: str
    total_score: Decimal


class GradingEngine:
    """
    Main grading engine with multi-pass evaluation.

    Performs multiple LLM passes and selects the median result
    to eliminate variance and ensure consistency.
    """

    def __init__(self, settings: Settings | None = None):
        """
        Initialize the grading engine.

        Args:
            settings: Configuration settings. Uses global settings if not provided.
        """
        self._settings = settings or get_settings()
        self._llm_client = LLMClient(self._settings)
        self._prompt_builder = PromptBuilder()
        self._response_parser = ResponseParser()

    def grade(
        self,
        rubric: Rubric,
        student_answer: str,
        strictness_mode: StrictnessMode | None = None,
        passes: int | None = None,
    ) -> tuple[GradingResult, AuditRecord]:
        """
        Grade a student answer against a rubric.

        Performs multi-pass grading and returns the median result.

        Args:
            rubric: The grading rubric.
            student_answer: The student's answer text.
            strictness_mode: Override strictness mode.
            passes: Override number of passes.

        Returns:
            Tuple of (GradingResult, AuditRecord).

        Raises:
            LLMError: If LLM calls fail.
            ScoringError: If response parsing fails.
        """
        mode = strictness_mode or self._settings.strictness_mode
        num_passes = passes or self._settings.grading_passes

        # Perform grading passes
        grading_passes = self._perform_passes(rubric, student_answer, mode, num_passes)

        # Select best result (median for multi-pass)
        final_result, variance_detected = self._select_result(grading_passes, rubric)

        # Update result with pass info
        final_result_with_meta = GradingResult(
            submission_id=final_result.submission_id,
            rubric_title=final_result.rubric_title,
            criteria_results=final_result.criteria_results,
            overall_feedback=final_result.overall_feedback,
            graded_at=datetime.utcnow(),
            llm_passes_used=num_passes,
            variance_detected=variance_detected,
            flagged_for_review=variance_detected
            and self._calculate_variance(grading_passes) > self._settings.max_variance_percent,
        )

        # Create audit record
        audit = self._create_audit(rubric, student_answer, final_result_with_meta)

        return final_result_with_meta, audit

    def _perform_passes(
        self,
        rubric: Rubric,
        student_answer: str,
        strictness_mode: StrictnessMode,
        num_passes: int,
    ) -> list[GradingPass]:
        """
        Perform multiple grading passes.

        Args:
            rubric: The grading rubric.
            student_answer: Student's answer.
            strictness_mode: Strictness mode.
            num_passes: Number of passes to perform.

        Returns:
            List of GradingPass results.
        """
        system_prompt = PromptBuilder.get_system_prompt()
        user_prompt = PromptBuilder.build_grading_prompt(rubric, student_answer, strictness_mode)

        passes: list[GradingPass] = []
        errors: list[Exception] = []

        for i in range(num_passes):
            try:
                # Get LLM response
                raw_response = self._llm_client.generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=self._settings.llm_temperature,
                )

                # Parse response
                result = self._response_parser.parse(raw_response, rubric)

                passes.append(
                    GradingPass(
                        result=result,
                        raw_response=raw_response,
                        total_score=result.total_awarded,
                    )
                )

            except (LLMError, ScoringError) as e:
                errors.append(e)
                # Continue with remaining passes
                continue

        # Need at least one successful pass
        if not passes:
            if errors:
                raise errors[0]
            raise LLMError("No successful grading passes completed")

        return passes

    def _select_result(
        self, passes: list[GradingPass], rubric: Rubric
    ) -> tuple[GradingResult, bool]:
        """
        Select the final result from multiple passes.

        For single pass, returns that pass.
        For multiple passes, returns the median result.

        Args:
            passes: List of grading passes.
            rubric: The rubric (for context).

        Returns:
            Tuple of (selected GradingResult, variance_detected).
        """
        if len(passes) == 1:
            return passes[0].result, False

        # Calculate scores
        scores = [float(p.total_score) for p in passes]

        # Detect variance
        variance_percent = self._calculate_variance(passes)
        variance_detected = variance_percent > self._settings.max_variance_percent

        # Find median score
        median_score = statistics.median(scores)

        # Select pass closest to median
        closest_pass = min(passes, key=lambda p: abs(float(p.total_score) - median_score))

        return closest_pass.result, variance_detected

    def _calculate_variance(self, passes: list[GradingPass]) -> float:
        """
        Calculate variance percentage between passes.

        Args:
            passes: List of grading passes.

        Returns:
            Variance as percentage of max score.
        """
        if len(passes) < 2:
            return 0.0

        scores = [float(p.total_score) for p in passes]
        max_possible = float(passes[0].result.total_max)

        if max_possible == 0:
            return 0.0

        score_range = max(scores) - min(scores)
        return (score_range / max_possible) * 100

    def _create_audit(
        self, rubric: Rubric, student_answer: str, result: GradingResult
    ) -> AuditRecord:
        """
        Create an audit record for the grading operation.

        Args:
            rubric: The rubric used.
            student_answer: The student's answer.
            result: The grading result.

        Returns:
            Immutable AuditRecord.
        """
        # Serialize rubric for hashing
        rubric_content = f"{rubric.title}\n" + "\n".join(
            f"{c.name}: {c.max_points} - {c.description}" for c in rubric.criteria
        )

        # Serialize result for hashing
        result_content = f"{result.total_awarded}/{result.total_max}\n" + "\n".join(
            f"{r.criterion_name}: {r.awarded_points}" for r in result.criteria_results
        )

        return AuditRecord(
            rubric_hash=AuditRecord.compute_hash(rubric_content),
            answer_hash=AuditRecord.compute_hash(student_answer),
            result_hash=AuditRecord.compute_hash(result_content),
            model_used=self._settings.zenmux_model,
            temperature=self._settings.llm_temperature,
            passes_count=result.llm_passes_used,
        )

    def health_check(self) -> bool:
        """
        Check if the grading engine is operational.

        Returns:
            True if LLM API is reachable.
        """
        return self._llm_client.health_check()
