"""LLM provider adapter hooks for customizing LLM configuration."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMProviderConfig:
    """LLM provider configuration."""

    provider: str
    model: str
    api_key_env: str
    timeout: int
    max_tokens: int
    temperature: float = 0.7
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        """Initialize metadata if not provided."""
        if self.metadata is None:
            self.metadata = {}


class LLMProviderAdapter(ABC):
    """Base class for LLM provider customization.

    Allows domains to customize LLM provider selection, model routing,
    and parameter tuning per domain requirements.

    Example:
        class TradingLLMAdapter(LLMProviderAdapter):
            async def adapt_config(self, base_config: LLMProviderConfig) -> LLMProviderConfig:
                # Use specialized model for trading analysis
                if self.task_type == "backtest_analysis":
                    config = LLMProviderConfig(
                        provider="anthropic",
                        model="claude-3-sonnet",  # Faster model for backtests
                        api_key_env="ANTHROPIC_API_KEY",
                        timeout=180,
                        max_tokens=2048,
                        temperature=0.5  # Lower temp for consistency
                    )
                return config

            async def should_retry(self, error: Exception) -> bool:
                # Retry on rate limits
                return "rate_limit" in str(error).lower()
    """

    @abstractmethod
    async def adapt_config(self, base_config: LLMProviderConfig) -> LLMProviderConfig:
        """Adapt LLM provider configuration.

        Args:
            base_config: Base configuration from Village

        Returns:
            Adapted configuration
        """
        pass

    @abstractmethod
    async def should_retry(self, error: Exception) -> bool:
        """Determine if failed LLM call should be retried.

        Args:
            error: Exception from LLM call

        Returns:
            True if call should be retried
        """
        pass

    @abstractmethod
    async def get_retry_delay(self, attempt: int) -> float:
        """Get delay for retry attempt.

        Args:
            attempt: Retry attempt number (1-based)

        Returns:
            Delay in seconds
        """
        pass


class DefaultLLMProviderAdapter(LLMProviderAdapter):
    """Default LLM provider adapter."""

    async def adapt_config(self, base_config: LLMProviderConfig) -> LLMProviderConfig:
        """Return config unchanged."""
        return base_config

    async def should_retry(self, error: Exception) -> bool:
        """Retry on certain error types."""
        error_str = str(error).lower()
        return any(
            keyword in error_str
            for keyword in ["timeout", "connection", "rate_limit", "temporarily"]
        )

    async def get_retry_delay(self, attempt: int) -> float:
        """Exponential backoff with jitter."""
        import random

        base_delay = 2**attempt
        jitter = random.uniform(0, 1)
        return base_delay + jitter  # type: ignore[no-any-return]
