from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TransportCapabilities:
    streaming: bool = False
    files: bool = False
    terminal: bool = False
    markdown: bool = False
    menus: bool = False
    persistence: bool = False


class AsyncTransport(ABC):
    @abstractmethod
    async def start(self) -> None:
        """Initialize transport (connect, start polling, etc.)."""

    @abstractmethod
    async def stop(self) -> None:
        """Shutdown transport cleanly."""

    @abstractmethod
    async def send(self, message: str) -> None:
        """Send message to user."""

    @abstractmethod
    async def receive(self) -> str:
        """Block until user sends a message. Return text content."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Transport identifier (e.g. 'cli', 'telegram')."""

    @property
    @abstractmethod
    def capabilities(self) -> TransportCapabilities:
        """Transport feature capabilities."""

    async def route(self, target_role: str, context: str | None = None) -> None:
        """Handle cross-role routing. Default: send as text message."""
        msg = f"Routing to {target_role}."
        if context:
            msg += f"\nContext: {context}"
        await self.send(msg)


def create_transport(
    name: str,
    config: Any = None,
    summarize_fn: Callable[[str], Awaitable[str]] | None = None,
) -> AsyncTransport:
    from village.chat.transports.cli import CLITransport

    if name == "cli":
        return CLITransport()
    elif name == "telegram":
        from village.chat.transports.telegram import TelegramTransport

        return TelegramTransport(config.telegram, summarize_fn=summarize_fn)
    elif name == "acp":
        raise ValueError("ACP transport runs as a daemon. Use 'village --transport acp' instead.")
    elif name == "stdio":
        from village.chat.transports.stdio import StdioTransport

        return StdioTransport()
    raise ValueError(f"Unknown transport: {name}")


def get_transport_names() -> list[str]:
    return ["cli", "telegram", "acp", "stdio"]
