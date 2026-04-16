from __future__ import annotations

import asyncio

import click

from village.chat.transports import AsyncTransport, TransportCapabilities


class CLITransport(AsyncTransport):
    @property
    def name(self) -> str:
        return "cli"

    @property
    def capabilities(self) -> TransportCapabilities:
        return TransportCapabilities(streaming=True, files=True, terminal=True)

    async def start(self) -> None:
        click.echo("Village Greeter — How can I help? /exit to quit.\n")

    async def stop(self) -> None:
        click.echo("\nExiting...")

    async def send(self, message: str) -> None:
        click.echo("\n" + message + "\n")

    async def receive(self) -> str:
        loop = asyncio.get_event_loop()
        user_input: str = await loop.run_in_executor(None, lambda: click.prompt("", prompt_suffix="> "))
        return user_input

    async def route(self, target_role: str, context: str | None = None) -> None:
        from typing import Any

        from village.roles import run_role_chat

        click.echo(f"\n  ── Routing to {target_role} ──────────")
        ctx: dict[str, Any] | None = {"context": context} if context else None
        run_role_chat(target_role, context=ctx)
