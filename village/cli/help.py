"""Help (ephemeral Q&A) and drafts commands."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

import click

from village.config import get_config
from village.logging import get_logger

if TYPE_CHECKING:
    from village.config import Config
    from village.extensibility import ExtensionRegistry, MCPServer

logger = get_logger(__name__)


async def _initialize_extensions_and_mcp(
    config: Config,
) -> tuple[ExtensionRegistry, list[MCPServer]]:
    from village.extensibility import (
        discover_mcp_servers,
        initialize_extensions,
    )

    extensions = await initialize_extensions(config)
    discovered_servers = await discover_mcp_servers(extensions)
    return extensions, discovered_servers


@click.command()
def help_cmd() -> None:
    """
    Start ephemeral LLM Q&A session.

    Interactive LLM session for asking questions about your project.
    No slash commands, no archival — just ask and get answers.

    Type /exit or /quit to end the session.
    """
    from village.chat.beads_client import BeadsClient, BeadsError
    from village.chat.llm_chat import LLMChat
    from village.llm.factory import get_llm_client

    config = get_config()

    try:
        beads_client = BeadsClient()
    except Exception:
        beads_client = None

    llm_client = get_llm_client(config)

    prompt_path = Path(__file__).parent.parent.parent / "prompts" / "chat" / "ppc_task_spec.md"
    try:
        with open(prompt_path, encoding="utf-8") as f:
            system_prompt = f.read()
    except FileNotFoundError:
        system_prompt = None

    llm_chat = LLMChat(llm_client, system_prompt=system_prompt, config=config)

    async def setup_chat() -> None:
        extensions, discovered_servers = await _initialize_extensions_and_mcp(config)

        await llm_chat.set_extensions(extensions)

        if beads_client:
            await llm_chat.set_beads_client(beads_client)

    try:
        asyncio.run(setup_chat())
    except Exception:
        pass

    click.echo("Village Help — Ask anything about your project. /exit to quit.\n")

    try:
        while True:
            user_input = click.prompt("", prompt_suffix="> ")

            if user_input.lower() in ["/exit", "/quit", "/bye"]:
                break

            try:
                response = asyncio.run(llm_chat.handle_message(user_input))
                click.echo("\n" + response + "\n")
            except BeadsError as e:
                click.echo(f"\n❌ Beads error: {e}\n")
            except Exception as e:
                click.echo(f"\n❌ Error: {e}\n")
    except click.exceptions.Abort:
        click.echo("\nExiting...")
    except KeyboardInterrupt:
        click.echo("\nExiting...")


@click.command()
@click.option("--scope", type=str, help="Filter by scope (feature|fix|investigation|refactoring)")
@click.option("--total", is_flag=True, help="Return draft count (for statusbar)")
def drafts(scope: str | None, total: bool) -> None:
    """
    List or count draft tasks.

    Default: Show 2-column table (ID, Title)

    Examples:
      village drafts
      village drafts --scope feature
      village drafts --total

    Flags:
      --scope: Filter by scope
      --total: Return count only (machine-readable)
    """
    from village.chat.drafts import list_drafts
    from village.render.text import render_drafts_table

    config = get_config()
    all_drafts = list_drafts(config)

    if total:
        click.echo(str(len(all_drafts)))
        return

    if scope:
        all_drafts = [d for d in all_drafts if d.scope == scope]

    output = render_drafts_table(all_drafts)
    click.echo(output)
