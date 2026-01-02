"""
Pydantic models for the Strict Grader system.

These models define the strict schemas for:
- Rubric criteria and structure
- Grading results with per-criterion scores
- Audit records for reproducibility

All models use strict validation to ensure data integrity.
"""

from datetime import datetime
from decimal import Decimal
from hashlib import sha256
from typing import Any
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)


# ==============================================================================
# Rubric Models
# ==============================================================================


class RubricCriterion(BaseModel):
    """
    A single grading criterion within a rubric.

    Each criterion has a name, description, and maximum points.
    The description must be clear and unambiguous for consistent grading.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Name of the criterion (e.g., 'Content Accuracy')",
    )

    description: str = Field(
        ...,
        min_length=1,
        description="Clear description of what this criterion evaluates",
    )

    max_points: Decimal = Field(
        ...,
        gt=0,
        le=1000,
        description="Maximum points for this criterion",
    )

    allows_partial_credit: bool = Field(
        default=True,
        description="Whether partial credit is allowed for this criterion",
    )

    @field_validator("max_points", mode="before")
    @classmethod
    def convert_to_decimal(cls, v: Any) -> Decimal:
        """Convert numeric values to Decimal for precision."""
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))


class Rubric(BaseModel):
    """
    A complete grading rubric with multiple criteria.

    The rubric is validated to ensure:
    - At least one criterion exists
    - Total points are consistent with criteria sum
    - No duplicate criterion names
    """

    model_config = ConfigDict(frozen=True, strict=True)

    title: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Title of the rubric",
    )

    description: str = Field(
        default="",
        description="Optional description of the rubric's purpose",
    )

    criteria: tuple[RubricCriterion, ...] = Field(
        ...,
        min_length=1,
        description="List of grading criteria",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_max_points(self) -> Decimal:
        """Calculate total maximum points from all criteria."""
        return sum((c.max_points for c in self.criteria), Decimal(0))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def criterion_count(self) -> int:
        """Return the number of criteria."""
        return len(self.criteria)

    @model_validator(mode="after")
    def validate_no_duplicate_names(self) -> "Rubric":
        """Ensure no duplicate criterion names."""
        names = [c.name for c in self.criteria]
        if len(names) != len(set(names)):
            duplicates = [n for n in names if names.count(n) > 1]
            raise ValueError(f"Duplicate criterion names found: {set(duplicates)}")
        return self


# ==============================================================================
# Grading Result Models
# ==============================================================================


class CriterionResult(BaseModel):
    """
    The grading result for a single criterion.

    Includes the score, justification, and any deduction reasons.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    criterion_name: str = Field(
        ...,
        description="Name of the criterion being evaluated",
    )

    max_points: Decimal = Field(
        ...,
        description="Maximum possible points for this criterion",
    )

    awarded_points: Decimal = Field(
        ...,
        ge=0,
        description="Points awarded (0 to max_points)",
    )

    justification: str = Field(
        ...,
        min_length=1,
        description="Specific justification for the score with quotes from answer",
    )

    deduction_reason: str | None = Field(
        default=None,
        description="Specific reason for any deductions, citing rubric requirements",
    )

    @field_validator("max_points", "awarded_points", mode="before")
    @classmethod
    def convert_to_decimal(cls, v: Any) -> Decimal:
        """Convert numeric values to Decimal for precision."""
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))

    @model_validator(mode="after")
    def validate_points_range(self) -> "CriterionResult":
        """Ensure awarded points don't exceed max points."""
        if self.awarded_points > self.max_points:
            raise ValueError(
                f"Awarded points ({self.awarded_points}) cannot exceed "
                f"max points ({self.max_points})"
            )
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def percentage(self) -> float:
        """Calculate percentage score for this criterion."""
        if self.max_points == 0:
            return 0.0
        return float(self.awarded_points / self.max_points * 100)


class GradingResult(BaseModel):
    """
    Complete grading result for a student submission.

    Contains per-criterion results, overall score, and feedback.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    submission_id: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for this grading result",
    )

    rubric_title: str = Field(
        ...,
        description="Title of the rubric used for grading",
    )

    criteria_results: tuple[CriterionResult, ...] = Field(
        ...,
        min_length=1,
        description="Results for each criterion",
    )

    overall_feedback: str = Field(
        ...,
        min_length=1,
        description="Constructive overall feedback for the student",
    )

    graded_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when grading was completed",
    )

    llm_passes_used: int = Field(
        default=1,
        ge=1,
        description="Number of LLM passes used for this result",
    )

    variance_detected: bool = Field(
        default=False,
        description="Whether significant variance was detected between passes",
    )

    flagged_for_review: bool = Field(
        default=False,
        description="Whether this result is flagged for human review",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_awarded(self) -> Decimal:
        """Calculate total awarded points."""
        return sum((r.awarded_points for r in self.criteria_results), Decimal(0))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_max(self) -> Decimal:
        """Calculate total maximum points."""
        return sum((r.max_points for r in self.criteria_results), Decimal(0))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def percentage_score(self) -> float:
        """Calculate overall percentage score."""
        if self.total_max == 0:
            return 0.0
        return float(self.total_awarded / self.total_max * 100)


# ==============================================================================
# Audit Models
# ==============================================================================


class AuditRecord(BaseModel):
    """
    Immutable audit record for reproducibility.

    Contains hashes of inputs and outputs to enable verification
    that the same inputs produce the same outputs.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    audit_id: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for this audit record",
    )

    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp of the grading operation",
    )

    rubric_hash: str = Field(
        ...,
        description="SHA-256 hash of the rubric content",
    )

    answer_hash: str = Field(
        ...,
        description="SHA-256 hash of the student answer content",
    )

    result_hash: str = Field(
        ...,
        description="SHA-256 hash of the grading result",
    )

    model_used: str = Field(
        ...,
        description="LLM model identifier used for grading",
    )

    temperature: float = Field(
        ...,
        description="Temperature setting used for LLM",
    )

    passes_count: int = Field(
        ...,
        description="Number of grading passes performed",
    )

    @staticmethod
    def compute_hash(content: str) -> str:
        """Compute SHA-256 hash of content."""
        return sha256(content.encode("utf-8")).hexdigest()


# ==============================================================================
# Document Extraction Models
# ==============================================================================


class ExtractedDocument(BaseModel):
    """
    Result of extracting text from a document.

    Contains the extracted text and metadata about the source.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    content: str = Field(
        ...,
        description="Extracted text content",
    )

    source_path: str = Field(
        ...,
        description="Path to the source document",
    )

    file_extension: str = Field(
        ...,
        description="File extension of the source document",
    )

    extraction_timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the extraction was performed",
    )

    character_count: int = Field(
        default=0,
        ge=0,
        description="Number of characters in extracted content",
    )

    @model_validator(mode="after")
    def set_character_count(self) -> "ExtractedDocument":
        """Set character count from content."""
        # Use object.__setattr__ because model is frozen
        object.__setattr__(self, "character_count", len(self.content))
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def content_hash(self) -> str:
        """Compute hash of the content for verification."""
        return AuditRecord.compute_hash(self.content)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_empty(self) -> bool:
        """Check if extracted content is empty or whitespace-only."""
        return len(self.content.strip()) == 0
