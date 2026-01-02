"""
Configuration management for the Strict Grader system.

Uses Pydantic Settings for type-safe configuration loading from environment variables.
All configuration is validated at startup to fail fast on misconfiguration.
"""

from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class StrictnessMode(str, Enum):
    """Strictness mode for grading."""

    PROPORTIONAL = "proportional"  # Points based on criteria met
    HARD_FAIL = "hard_fail"  # No partial credit, full deduction on any miss


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All settings are validated at startup. Missing required fields
    will raise clear validation errors.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ==========================================================================
    # ZenMux API Configuration
    # ==========================================================================
    zenmux_api_key: str = Field(
        ...,
        description="API key for ZenMux (OpenAI-compatible endpoint)",
        min_length=10,
    )

    zenmux_base_url: str = Field(
        default="https://zenmux.ai/api/v1",
        description="Base URL for the ZenMux API",
    )

    zenmux_model: str = Field(
        default="google/gemini-3-flash-preview",
        description="Model to use for grading",
    )

    # ==========================================================================
    # Grading Configuration
    # ==========================================================================
    grading_passes: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Number of grading passes for multi-pass evaluation",
    )

    llm_temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Temperature for LLM generation (0.0 = deterministic)",
    )

    max_variance_percent: float = Field(
        default=5.0,
        ge=0.0,
        le=100.0,
        description="Maximum allowed variance between passes before flagging",
    )

    strictness_mode: StrictnessMode = Field(
        default=StrictnessMode.PROPORTIONAL,
        description="Strictness mode for grading",
    )

    # ==========================================================================
    # File Processing Configuration
    # ==========================================================================
    max_file_size_mb: float = Field(
        default=10.0,
        ge=0.1,
        le=100.0,
        description="Maximum allowed file size in megabytes",
    )

    supported_extensions: tuple[str, ...] = Field(
        default=(".txt", ".md", ".docx", ".doc", ".pdf", ".xlsx", ".xls"),
        description="Supported file extensions for document extraction",
    )

    # ==========================================================================
    # Output Configuration
    # ==========================================================================
    output_directory: Path = Field(
        default=Path("./output"),
        description="Directory for output reports",
    )

    @field_validator("zenmux_base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """Ensure base URL doesn't have trailing slash."""
        return v.rstrip("/")

    @field_validator("output_directory")
    @classmethod
    def validate_output_directory(cls, v: Path) -> Path:
        """Ensure output directory exists or can be created."""
        v.mkdir(parents=True, exist_ok=True)
        return v


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Uses LRU cache to ensure settings are only loaded once.
    """
    return Settings()
