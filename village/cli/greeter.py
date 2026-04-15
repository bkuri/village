from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import TYPE_CHECKING

import click

from village.config import get_config
from village.logging import get_logger
from village.roles import RoleChat, RoutingAction, run_role_chat

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
@click.option(
    "--model",
    type=str,
    default=None,
    help="Model override for the LLM (e.g., openrouter/openai/o3-mini)",
)
@click.option(
    "--no-system-prompt",
    is_flag=True,
    help="Disable the PPC Task Spec system prompt",
)
def greeter(model: str | None, no_system_prompt: bool) -> None:
    config = get_config()

    if model and model.startswith("openrouter/"):
        from village.llm.providers.openrouter import OpenRouterClient

        api_key = os.getenv(config.llm.api_key_env)
        if not api_key:
            raise click.ClickException("OpenRouter API key not set.")
        llm_client = OpenRouterClient(api_key=api_key, model=model.replace("openrouter/", ""))
        click.echo(f"  Using model: {model}")
    elif model and model.startswith("anthropic/"):
        from village.llm.providers.anthropic import AnthropicClient

        api_key = os.getenv(config.llm.api_key_env)
        if not api_key:
            raise click.ClickException("Anthropic API key not set.")
        llm_client = AnthropicClient(api_key=api_key, model=model.replace("anthropic/", ""))
        click.echo(f"  Using model: {model}")
    else:
        from village.llm.factory import get_llm_client

        if model:
            click.echo(f"  Using model: {model}")
        llm_client = get_llm_client(config)

    system_prompt = None
    if not no_system_prompt:
        prompt_path = Path(__file__).parent.parent.parent / "prompts" / "chat" / "ppc_task_spec.md"
        try:
            with open(prompt_path, encoding="utf-8") as f:
                system_prompt = f.read()
        except FileNotFoundError:
            pass

    from village.chat.llm_chat import LLMChat

    llm_chat = LLMChat(llm_client, system_prompt=system_prompt, config=config)

    async def setup_chat() -> None:
        extensions, discovered_servers = await _initialize_extensions_and_mcp(config)
        await llm_chat.set_extensions(extensions)

    try:
        asyncio.run(setup_chat())
    except Exception:
        pass

    click.echo("Village Greeter — How can I help? /exit to quit.\n")

    role_chat = RoleChat("greeter")

    try:
        while True:
            user_input = click.prompt("", prompt_suffix="> ")

            if user_input.lower() in ["/exit", "/quit", "/bye"]:
                break

            try:
                response = asyncio.run(llm_chat.handle_message(user_input))
            except Exception as e:
                click.echo(f"\n❌ Error: {e}\n")
                continue

            routing = role_chat.detect_cross_role(response)
            if routing and routing.target_role:
                if routing.action == RoutingAction.ROUTE:
                    click.echo(f"\n  ── Routing to {routing.target_role} ──────────")
                    run_role_chat(routing.target_role, context=routing.context)
                    break
                elif routing.action == RoutingAction.ADVISE:
                    click.echo(f"\n  That sounds like a job for the {routing.target_role}.")
                    confirm = click.prompt("  Want me to start it? [Y/n]", default="Y")
                    if confirm.strip().lower() in ("y", "yes", ""):
                        click.echo(f"  ── Routing to {routing.target_role} ──────────")
                        run_role_chat(routing.target_role, context=routing.context)
                        break
                    else:
                        click.echo(f"  You can run: village {routing.target_role}\n")
                        continue

            click.echo("\n" + response + "\n")
    except click.exceptions.Abort:
        click.echo("\nExiting...")
    except KeyboardInterrupt:
        click.echo("\nExiting...")


@click.command()
@click.option("--scope", type=str, help="Filter by scope (feature|fix|investigation|refactoring)")
@click.option("--total", is_flag=True, help="Return draft count (for statusbar)")
def drafts(scope: str | None, total: bool) -> None:
    """List or count draft tasks."""
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
