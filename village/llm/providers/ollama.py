"""Ollama provider implementation."""

import logging
from typing import Optional

import httpx

from village.llm.client import LLMClient, ToolDefinition

logger = logging.getLogger(__name__)


class OllamaClient(LLMClient):
    """Ollama local client (no tool support)."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "mistral",
    ):
        """Initialize Ollama client.

        Args:
            base_url: Ollama server URL
            model: Model name to use
        """
        self.base_url = base_url
        self.model = model

    def call(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tools: Optional[list[ToolDefinition]] = None,
        max_tokens: int = 4096,
        timeout: int = 300,
    ) -> str:
        """Call Ollama API (no tool support).

        Args:
            prompt: User prompt
            system_prompt: System message (appended to prompt)
            tools: Not supported by Ollama (ignored)
            max_tokens: Not supported by Ollama (ignored)
            timeout: Call timeout in seconds

        Returns:
            LLM response
        """
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "stream": False,
        }

        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                )
                response.raise_for_status()

                data = response.json()
                response_str = data.get("response", "")
                return str(response_str)

        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama API error: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Ollama request error: {e}")
            raise
        except KeyError as e:
            logger.error(f"Ollama response parsing error: {e}")
            raise

    @property
    def supports_tools(self) -> bool:
        """Ollama doesn't support tool calling."""
        return False

    @property
    def supports_mcp(self) -> bool:
        """Ollama doesn't support MCP."""
        return False
