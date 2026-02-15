"""Test LLMProviderAdapter ABC and DefaultLLMProviderAdapter."""

import pytest

from village.extensibility.llm_adapters import (
    DefaultLLMProviderAdapter,
    LLMProviderAdapter,
    LLMProviderConfig,
)


class TestLLMProviderConfig:
    """Test LLMProviderConfig dataclass."""

    def test_llm_provider_config_initialization(self):
        """Test LLMProviderConfig initialization with required fields."""
        config = LLMProviderConfig(
            provider="anthropic",
            model="claude-3-opus",
            api_key_env="ANTHROPIC_API_KEY",
            timeout=120,
            max_tokens=4096,
        )
        assert config.provider == "anthropic"
        assert config.model == "claude-3-opus"
        assert config.api_key_env == "ANTHROPIC_API_KEY"
        assert config.timeout == 120
        assert config.max_tokens == 4096
        assert config.temperature == 0.7
        assert config.metadata == {}

    def test_llm_provider_config_with_temperature(self):
        """Test LLMProviderConfig with custom temperature."""
        config = LLMProviderConfig(
            provider="openai",
            model="gpt-4",
            api_key_env="OPENAI_API_KEY",
            timeout=60,
            max_tokens=2048,
            temperature=0.5,
        )
        assert config.temperature == 0.5

    def test_llm_provider_config_with_metadata(self):
        """Test LLMProviderConfig with metadata."""
        metadata = {"region": "us-east", "tier": "premium"}
        config = LLMProviderConfig(
            provider="anthropic",
            model="claude-3-opus",
            api_key_env="ANTHROPIC_API_KEY",
            timeout=120,
            max_tokens=4096,
            metadata=metadata,
        )
        assert config.metadata == metadata

    def test_llm_provider_config_all_fields(self):
        """Test LLMProviderConfig with all fields."""
        metadata = {"custom": "value"}
        config = LLMProviderConfig(
            provider="ollama",
            model="llama2",
            api_key_env="Ollama_API_KEY",
            timeout=300,
            max_tokens=8192,
            temperature=0.8,
            metadata=metadata,
        )

        assert config.provider == "ollama"
        assert config.model == "llama2"
        assert config.api_key_env == "Ollama_API_KEY"
        assert config.timeout == 300
        assert config.max_tokens == 8192
        assert config.temperature == 0.8
        assert config.metadata == metadata

    def test_llm_provider_config_none_metadata_becomes_empty(self):
        """Test that None metadata becomes empty dict via post_init."""
        config = LLMProviderConfig(
            provider="anthropic",
            model="claude-3-opus",
            api_key_env="ANTHROPIC_API_KEY",
            timeout=120,
            max_tokens=4096,
            metadata=None,
        )
        assert config.metadata == {}

    def test_llm_provider_config_temperature_default(self):
        """Test that temperature defaults to 0.7."""
        config = LLMProviderConfig(
            provider="anthropic",
            model="claude-3-opus",
            api_key_env="ANTHROPIC_API_KEY",
            timeout=120,
            max_tokens=4096,
        )
        assert config.temperature == 0.7

    def test_llm_provider_config_mutation(self):
        """Test that LLMProviderConfig fields can be mutated."""
        config = LLMProviderConfig(
            provider="anthropic",
            model="claude-3-opus",
            api_key_env="ANTHROPIC_API_KEY",
            timeout=120,
            max_tokens=4096,
        )
        config.metadata["new_key"] = "new_value"

        assert config.metadata["new_key"] == "new_value"

    def test_llm_provider_config_valid_providers(self):
        """Test LLMProviderConfig with various providers."""
        providers = ["anthropic", "openai", "ollama", "openrouter"]

        for provider in providers:
            config = LLMProviderConfig(
                provider=provider,
                model="test-model",
                api_key_env="API_KEY",
                timeout=60,
                max_tokens=2048,
            )
            assert config.provider == provider


class TestDefaultLLMProviderAdapter:
    """Test DefaultLLMProviderAdapter behavior."""

    @pytest.mark.asyncio
    async def test_adapt_config_returns_unchanged(self):
        """Test that adapt_config returns config unchanged."""
        adapter = DefaultLLMProviderAdapter()
        config = LLMProviderConfig(
            provider="anthropic",
            model="claude-3-opus",
            api_key_env="ANTHROPIC_API_KEY",
            timeout=120,
            max_tokens=4096,
        )

        result = await adapter.adapt_config(config)

        assert result is config
        assert result.provider == "anthropic"
        assert result.model == "claude-3-opus"

    @pytest.mark.asyncio
    async def test_adapt_config_with_different_configs(self):
        """Test adapt_config with different configs."""
        adapter = DefaultLLMProviderAdapter()

        configs = [
            LLMProviderConfig(
                provider="anthropic",
                model="claude-3-opus",
                api_key_env="KEY1",
                timeout=120,
                max_tokens=4096,
            ),
            LLMProviderConfig(
                provider="openai",
                model="gpt-4",
                api_key_env="KEY2",
                timeout=60,
                max_tokens=2048,
            ),
        ]

        for config in configs:
            result = await adapter.adapt_config(config)
            assert result is config

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


class TestCustomLLMProviderAdapter:
    """Test custom LLMProviderAdapter implementations."""

    @pytest.mark.asyncio
    async def test_custom_adapter_modifies_config(self):
        """Test custom adapter that modifies config."""

        class ModifyingAdapter(LLMProviderAdapter):
            async def adapt_config(self, base_config: LLMProviderConfig) -> LLMProviderConfig:
                return LLMProviderConfig(
                    provider="anthropic",
                    model="claude-3-sonnet",
                    api_key_env=base_config.api_key_env,
                    timeout=180,
                    max_tokens=2048,
                    temperature=0.5,
                )

            async def should_retry(self, error: Exception) -> bool:
                return False

            async def get_retry_delay(self, attempt: int) -> float:
                return 1.0

        adapter = ModifyingAdapter()
        base_config = LLMProviderConfig(
            provider="openai",
            model="gpt-4",
            api_key_env="OPENAI_KEY",
            timeout=60,
            max_tokens=4096,
        )

        adapted = await adapter.adapt_config(base_config)

        assert adapted.provider == "anthropic"
        assert adapted.model == "claude-3-sonnet"
        assert adapted.timeout == 180
        assert adapted.max_tokens == 2048
        assert adapted.temperature == 0.5

    @pytest.mark.asyncio
    async def test_custom_adapter_custom_retry_logic(self):
        """Test custom adapter with custom retry logic."""

        class CustomRetryAdapter(LLMProviderAdapter):
            async def adapt_config(self, base_config: LLMProviderConfig) -> LLMProviderConfig:
                return base_config

            async def should_retry(self, error: Exception) -> bool:
                error_str = str(error).lower()
                return "temporary" in error_str or "overloaded" in error_str

            async def get_retry_delay(self, attempt: int) -> float:
                return attempt * 2.0

        adapter = CustomRetryAdapter()

        assert await adapter.should_retry(Exception("Temporary error")) is True
        assert await adapter.should_retry(Exception("Server overloaded")) is True
        assert await adapter.should_retry(Exception("Rate limit")) is False

        delay = await adapter.get_retry_delay(3)
        assert delay == 6.0

    @pytest.mark.asyncio
    async def test_custom_adapter_with_task_based_config(self):
        """Test custom adapter that adapts config based on task."""

        class TaskBasedAdapter(LLMProviderAdapter):
            def __init__(self, task_type: str):
                self.task_type = task_type

            async def adapt_config(self, base_config: LLMProviderConfig) -> LLMProviderConfig:
                if self.task_type == "backtest_analysis":
                    return LLMProviderConfig(
                        provider="anthropic",
                        model="claude-3-sonnet",
                        api_key_env=base_config.api_key_env,
                        timeout=180,
                        max_tokens=2048,
                        temperature=0.5,
                    )
                elif self.task_type == "complex_analysis":
                    return LLMProviderConfig(
                        provider="anthropic",
                        model="claude-3-opus",
                        api_key_env=base_config.api_key_env,
                        timeout=300,
                        max_tokens=8192,
                        temperature=0.7,
                    )
                return base_config

            async def should_retry(self, error: Exception) -> bool:
                return True

            async def get_retry_delay(self, attempt: int) -> float:
                return 1.0

        backtest_adapter = TaskBasedAdapter("backtest_analysis")
        complex_adapter = TaskBasedAdapter("complex_analysis")

        base = LLMProviderConfig(
            provider="anthropic",
            model="claude-3-opus",
            api_key_env="KEY",
            timeout=120,
            max_tokens=4096,
        )

        backtest_config = await backtest_adapter.adapt_config(base)
        assert backtest_config.model == "claude-3-sonnet"
        assert backtest_config.timeout == 180
        assert backtest_config.temperature == 0.5

        complex_config = await complex_adapter.adapt_config(base)
        assert complex_config.model == "claude-3-opus"
        assert complex_config.timeout == 300
        assert complex_config.max_tokens == 8192
        assert complex_config.temperature == 0.7

    @pytest.mark.asyncio
    async def test_custom_adapter_with_state(self):
        """Test custom adapter that maintains state."""

        class StatefulAdapter(LLMProviderAdapter):
            def __init__(self):
                self.retry_count = 0

            async def adapt_config(self, base_config: LLMProviderConfig) -> LLMProviderConfig:
                return base_config

            async def should_retry(self, error: Exception) -> bool:
                self.retry_count += 1
                return self.retry_count < 3

            async def get_retry_delay(self, attempt: int) -> float:
                return attempt * 1.5

        adapter = StatefulAdapter()

        assert await adapter.should_retry(Exception("Error")) is True
        assert adapter.retry_count == 1

        assert await adapter.should_retry(Exception("Error")) is True
        assert adapter.retry_count == 2

        assert await adapter.should_retry(Exception("Error")) is False
        assert adapter.retry_count == 3


class TestLLMProviderAdapterABC:
    """Test that LLMProviderAdapter ABC cannot be instantiated directly."""

    def test_llm_provider_adapter_cannot_be_instantiated(self):
        """Test that abstract LLMProviderAdapter cannot be instantiated."""
        with pytest.raises(TypeError):
            LLMProviderAdapter()

    def test_custom_adapter_must_implement_all_methods(self):
        """Test that custom adapter must implement all abstract methods."""

        class IncompleteAdapter(LLMProviderAdapter):
            async def adapt_config(self, base_config: LLMProviderConfig) -> LLMProviderConfig:
                return base_config

            async def should_retry(self, error: Exception) -> bool:
                return True

        with pytest.raises(TypeError):
            IncompleteAdapter()
