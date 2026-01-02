"""
LLM Client for ZenMux API.

Provides a wrapper around the OpenAI SDK configured for ZenMux endpoints.
Includes retry logic, error handling, and rate limiting.
"""

import time
from typing import Any

from openai import APIConnectionError, APIStatusError, OpenAI, RateLimitError

from src.config import Settings, get_settings


class LLMError(Exception):
    """Raised when LLM API call fails."""

    def __init__(self, message: str, cause: Exception | None = None, retryable: bool = False):
        self.cause = cause
        self.retryable = retryable
        super().__init__(message)


class LLMClient:
    """
    Client for interacting with ZenMux LLM API.

    Uses OpenAI SDK with custom base URL for ZenMux compatibility.
    Implements retry logic with exponential backoff.
    """

    def __init__(self, settings: Settings | None = None):
        """
        Initialize the LLM client.

        Args:
            settings: Configuration settings. Uses global settings if not provided.
        """
        self._settings = settings or get_settings()
        self._client = OpenAI(
            api_key=self._settings.zenmux_api_key,
            base_url=self._settings.zenmux_base_url,
        )

        # Retry configuration
        self._max_retries = 3
        self._base_delay = 1.0  # seconds
        self._max_delay = 30.0  # seconds

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float | None = None,
        max_tokens: int = 8192,
    ) -> str:
        """
        Generate a response from the LLM.

        Args:
            system_prompt: System message defining the LLM's role.
            user_prompt: User message with the actual request.
            temperature: Override temperature (uses config default if None).
            max_tokens: Maximum tokens in response.

        Returns:
            The generated text response.

        Raises:
            LLMError: If generation fails after all retries.
        """
        temp = temperature if temperature is not None else self._settings.llm_temperature

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        return self._call_with_retry(messages, temp, max_tokens)

    def _call_with_retry(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> str:
        """
        Call the API with exponential backoff retry.

        Args:
            messages: Chat messages to send.
            temperature: Temperature setting.
            max_tokens: Maximum response tokens.

        Returns:
            Generated text.

        Raises:
            LLMError: If all retries fail.
        """
        last_error: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.chat.completions.create(
                    model=self._settings.zenmux_model,
                    messages=messages,  # type: ignore[arg-type]
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

                # Extract content from response
                if response.choices and response.choices[0].message.content:
                    return response.choices[0].message.content

                raise LLMError("Empty response from LLM")

            except RateLimitError as e:
                last_error = e
                delay = self._calculate_delay(attempt)
                if attempt < self._max_retries:
                    time.sleep(delay)
                    continue
                raise LLMError(
                    f"Rate limit exceeded after {self._max_retries} retries",
                    cause=e,
                    retryable=True,
                ) from e

            except APIConnectionError as e:
                last_error = e
                delay = self._calculate_delay(attempt)
                if attempt < self._max_retries:
                    time.sleep(delay)
                    continue
                raise LLMError(
                    f"Connection failed after {self._max_retries} retries",
                    cause=e,
                    retryable=True,
                ) from e

            except APIStatusError as e:
                # Don't retry on client errors (4xx except 429)
                if 400 <= e.status_code < 500 and e.status_code != 429:
                    raise LLMError(
                        f"API error: {e.message}",
                        cause=e,
                        retryable=False,
                    ) from e

                last_error = e
                delay = self._calculate_delay(attempt)
                if attempt < self._max_retries:
                    time.sleep(delay)
                    continue
                raise LLMError(
                    f"API error after {self._max_retries} retries: {e.message}",
                    cause=e,
                    retryable=True,
                ) from e

            except Exception as e:
                raise LLMError(f"Unexpected error: {e}", cause=e, retryable=False) from e

        # Should not reach here, but just in case
        raise LLMError(f"Failed after {self._max_retries} retries", cause=last_error)

    def _calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for exponential backoff.

        Args:
            attempt: Current attempt number (0-indexed).

        Returns:
            Delay in seconds.
        """
        delay = self._base_delay * (2**attempt)
        return min(delay, self._max_delay)

    def health_check(self) -> bool:
        """
        Check if the API is reachable.

        Returns:
            True if API is healthy, False otherwise.
        """
        try:
            response = self._client.chat.completions.create(
                model=self._settings.zenmux_model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
            )
            return bool(response.choices)
        except Exception:
            return False
