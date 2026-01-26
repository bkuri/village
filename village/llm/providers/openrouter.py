"""OpenRouter provider implementation."""

import logging
from typing import Optional

import httpx

from village.llm.client import LLMClient, ToolDefinition

logger = logging.getLogger(__name__)


class OpenRouterClient(LLMClient):
    """OpenRouter API client (OpenAI-compatible)."""

    def __init__(
        self,
        api_key: str,
        model: str = "anthropic/claude-3.5-sonnet",
        base_url: str = "https://openrouter.ai/api/v1",
    ):
        """Initialize OpenRouter client.

        Args:
            api_key: OpenRouter API key
            model: Model name to use
            base_url: OpenRouter API base URL
        """
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

    def call(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tools: Optional[list[ToolDefinition]] = None,
        max_tokens: int = 4096,
        timeout: int = 300,
    ) -> str:
        """Call OpenRouter API (OpenAI-compatible).

        Args:
            prompt: User prompt
            system_prompt: System message
            tools: Available tools (if model supports function calling)
            max_tokens: Max response tokens
            timeout: Call timeout in seconds

        Returns:
            LLM response
        """
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/anomalyco/village",
            "X-Title": "Village",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
        }

        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.input_schema,
                    },
                }
                for t in tools
            ]

        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()

                data = response.json()
                content = data["choices"][0]["message"]["content"]

                return str(content)
        except httpx.HTTPStatusError as e:
            logger.error(f"OpenRouter API error: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"OpenRouter request error: {e}")
            raise
        except (KeyError, IndexError) as e:
            logger.error(f"OpenRouter response parsing error: {e}")
            raise

    @property
    def supports_tools(self) -> bool:
        """OpenRouter supports tools if model supports them."""
        return True

    @property
    def supports_mcp(self) -> bool:
        """OpenRouter doesn't have native MCP support."""
        return False
