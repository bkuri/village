import logging
from typing import Optional

import httpx

from village.llm.client import LLMClient, ToolDefinition

logger = logging.getLogger(__name__)


class OpenRouterClient(LLMClient):
    def __init__(
        self,
        api_key: str,
        model: str = "anthropic/claude-3.5-sonnet",
        base_url: str = "https://openrouter.ai/api/v1",
    ):
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
        return True

    @property
    def supports_mcp(self) -> bool:
        return False


class AnthropicClient(LLMClient):
    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-5-sonnet-20241022",
        base_url: str = "https://api.anthropic.com",
    ):
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
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }

        messages = [{"role": "user", "content": prompt}]

        payload: dict = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages,
        }

        if system_prompt:
            payload["system"] = system_prompt

        if tools:
            payload["tools"] = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.input_schema,
                }
                for t in tools
            ]

        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    f"{self.base_url}/v1/messages",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()

                data = response.json()
                content = data["content"][0]["text"]
                return str(content)
        except httpx.HTTPStatusError as e:
            logger.error(f"Anthropic API error: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Anthropic request error: {e}")
            raise
        except (KeyError, IndexError) as e:
            logger.error(f"Anthropic response parsing error: {e}")
            raise

    @property
    def supports_tools(self) -> bool:
        return True

    @property
    def supports_mcp(self) -> bool:
        return False
