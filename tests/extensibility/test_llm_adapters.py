"""Test LLMProviderAdapter ABC and DefaultLLMProviderAdapter."""

import pytest

from village.extensibility.llm_adapters import (
    DefaultLLMProviderAdapter,
    LLMProviderConfig,
)


class TestDefaultLLMProviderAdapter:
    """Test DefaultLLMProviderAdapter behavior."""

    @pytest.mark.asyncio
    async def test_should_retry_with_timeout_error(self):
        """Test should_retry returns True for timeout errors."""
        adapter = DefaultLLMProviderAdapter()
        error = Exception("Request timeout")

        result = await adapter.should_retry(error)
        assert result is True

    @pytest.mark.asyncio
    async def test_should_retry_with_connection_error(self):
        """Test should_retry returns True for connection errors."""
        adapter = DefaultLLMProviderAdapter()
        error = Exception("Connection failed")

        result = await adapter.should_retry(error)
        assert result is True

    @pytest.mark.asyncio
    async def test_should_retry_with_rate_limit_error(self):
        """Test should_retry returns True for rate limit errors."""
        adapter = DefaultLLMProviderAdapter()
        error = Exception("Rate_limit exceeded")

        result = await adapter.should_retry(error)
        assert result is True

    @pytest.mark.asyncio
    async def test_should_retry_with_temporarily_error(self):
        """Test should_retry returns True for temporarily errors."""
        adapter = DefaultLLMProviderAdapter()
        error = Exception("Service temporarily unavailable")

        result = await adapter.should_retry(error)
        assert result is True

    @pytest.mark.asyncio
    async def test_should_retry_with_other_error(self):
        """Test should_retry returns False for other errors."""
        adapter = DefaultLLMProviderAdapter()
        error = Exception("Invalid API key")

        result = await adapter.should_retry(error)
        assert result is False

    @pytest.mark.asyncio
    async def test_should_retry_case_insensitive(self):
        """Test should_retry is case insensitive."""
        adapter = DefaultLLMProviderAdapter()

        errors = [
            Exception("TIMEOUT"),
            Exception("Timeout"),
            Exception("timeout"),
            Exception("CONNECTION ERROR"),
            Exception("Connection Error"),
            Exception("RATE_LIMIT"),
            Exception("Rate_Limit"),
        ]

        for error in errors:
            result = await adapter.should_retry(error)
            assert result is True

    @pytest.mark.asyncio
    async def test_get_retry_delay_exponential_backoff(self):
        """Test get_retry_delay uses exponential backoff."""
        adapter = DefaultLLMProviderAdapter()

        delay1 = await adapter.get_retry_delay(1)
        delay2 = await adapter.get_retry_delay(2)
        delay3 = await adapter.get_retry_delay(3)

        assert delay2 > delay1
        assert delay3 > delay2
        assert delay1 >= 2.0
        assert delay2 >= 4.0
        assert delay3 >= 8.0

    @pytest.mark.asyncio
    async def test_get_retry_delay_with_jitter(self):
        """Test get_retry_delay adds jitter."""
        adapter = DefaultLLMProviderAdapter()

        delays = []
        for _ in range(10):
            delay = await adapter.get_retry_delay(2)
            delays.append(delay)

        assert len(set(delays)) > 1
        assert all(4.0 <= d < 5.0 for d in delays)

    @pytest.mark.asyncio
    async def test_get_retry_delay_for_attempt_number(self):
        """Test get_retry_delay for various attempt numbers."""
        adapter = DefaultLLMProviderAdapter()

        for attempt in range(1, 6):
            delay = await adapter.get_retry_delay(attempt)
            base_delay = 2**attempt
            assert base_delay <= delay < base_delay + 1

    @pytest.mark.asyncio
    async def test_full_retry_workflow(self):
        """Test full retry workflow."""
        adapter = DefaultLLMProviderAdapter()
        config = LLMProviderConfig(
            provider="anthropic",
            model="claude-3-opus",
            api_key_env="KEY",
            timeout=120,
            max_tokens=4096,
        )

        adapted_config = await adapter.adapt_config(config)
        assert adapted_config is config

        timeout_error = Exception("Request timeout")
        should_retry = await adapter.should_retry(timeout_error)
        assert should_retry is True

        delay = await adapter.get_retry_delay(1)
        assert 2.0 <= delay < 3.0
