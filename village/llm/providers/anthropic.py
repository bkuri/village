"""Anthropic provider implementation."""

import logging
from typing import Optional

from anthropic import Anthropic, AnthropicError

from village.llm.client import LLMClient, ToolDefinition

logger = logging.getLogger(__name__)


class AnthropicClient(LLMClient):
    """Anthropic API client with tool support."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-5-sonnet-20241022",
    ):
        """Initialize Anthropic client.

        Args:
            api_key: Anthropic API key
            model: Model name to use
        """
        self.client = Anthropic(api_key=api_key)  # type: ignore[misc]
        self.model = model

    def call(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tools: Optional[list[ToolDefinition]] = None,
        max_tokens: int = 4096,
        timeout: int = 300,
    ) -> str:
        """Call Anthropic API with optional tool support.

        Args:
            prompt: User prompt
            system_prompt: System message
            tools: Available tools (Anthropic supports native tool use)
            max_tokens: Max response tokens
            timeout: Call timeout in seconds

        Returns:
            LLM response
        """
        messages = [{"role": "user", "content": prompt}]

        kwargs: dict[str, object] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "timeout": timeout,
        }

        if system_prompt:
            kwargs["system"] = system_prompt

        if tools:
            kwargs["tools"] = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.input_schema,
                }
                for t in tools
            ]

        try:
            response = self.client.messages.create(**kwargs)

            content_blocks = response.content
            text_parts = [block.text for block in content_blocks if hasattr(block, "text")]

            return "\n\n".join(text_parts)
        except AnthropicError as e:
            logger.error(f"Anthropic API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected Anthropic client error: {e}")
            raise

    @property
    def supports_tools(self) -> bool:
        """Anthropic supports native tool use."""
        return True

    @property
    def supports_mcp(self) -> bool:
        """Anthropic has MCP server support."""
        return True
