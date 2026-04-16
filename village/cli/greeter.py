from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import TYPE_CHECKING

import click

from village.chat.transports import create_transport
from village.config import get_config
from village.dispatch import dispatch
from village.errors import GracefulExit
from village.logging import get_logger
from village.roles import RoleChat, RoutingAction

if TYPE_CHECKING:
    from village.config import Config
    from village.extensibility import ExtensionRegistry, MCPServer
    from village.llm.client import LLMClient

logger = get_logger(__name__)


def _build_llm_client(model: str | None, config: Config, max_tokens: int | None = None) -> LLMClient:
    if model and model.startswith("openrouter/"):
        from village.llm.providers.openrouter import OpenRouterClient

        api_key = os.getenv(config.llm.api_key_env)
        if not api_key:
            raise click.ClickException("OpenRouter API key not set.")
        return OpenRouterClient(
            api_key=api_key,
            model=model.removeprefix("openrouter/"),
            max_tokens=max_tokens or 8192,
        )

    if model and model.startswith("anthropic/"):
        from village.llm.providers.anthropic import AnthropicClient

        api_key = os.getenv(config.llm.api_key_env)
        if not api_key:
            raise click.ClickException("Anthropic API key not set.")
        return AnthropicClient(
            api_key=api_key,
            model=model.removeprefix("anthropic/"),
            max_tokens=max_tokens or 8192,
        )

    from village.llm.factory import get_llm_client

    return get_llm_client(config)


def _load_system_prompt() -> str | None:
    prompt_path = Path(__file__).parent.parent.parent / "prompts" / "chat" / "ppc_task_spec.md"
    try:
        with open(prompt_path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


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


async def run_greeter(
    config: Config,
    transport_name: str,
    model: str | None,
    no_system_prompt: bool,
    max_tokens: int | None = None,
) -> None:
    if model:
        click.echo(f"  Using model: {model}")

    llm_client = _build_llm_client(model, config, max_tokens)
    transport = create_transport(transport_name, config)
    system_prompt = None if no_system_prompt else _load_system_prompt()

    from village.chat.llm_chat import LLMChat

    llm_chat = LLMChat(llm_client, system_prompt=system_prompt, config=config)

    try:
        extensions, _ = await _initialize_extensions_and_mcp(config)
        await llm_chat.set_extensions(extensions)
    except Exception:
        pass

    await transport.start()

    role_chat = RoleChat("greeter")
    exit_commands = frozenset({"/exit", "/quit", "/bye"})

    try:
        while True:
            user_input = await transport.receive()

            if user_input.strip().lower() in exit_commands:
                break

            result = await dispatch(transport, user_input, ctx={"config": config})
            if result is not None:
                await transport.send(result)
                continue

            try:
                response = await llm_chat.handle_message(user_input)
            except Exception as e:
                await transport.send(f"\n❌ Error: {e}\n")
                continue

            routing = role_chat.detect_cross_role(response)
            if routing and routing.target_role:
                if routing.action == RoutingAction.ROUTE:
                    await transport.route(routing.target_role, context=routing.message)
                    break
                elif routing.action == RoutingAction.ADVISE:
                    await transport.send(f"\n  That sounds like a job for the {routing.target_role}.")
                    confirm = await transport.receive()
                    if confirm.strip().lower() in ("y", "yes", ""):
                        await transport.route(routing.target_role, context=routing.message)
                        break
                    else:
                        await transport.send(f"  You can run: village {routing.target_role}\n")
                        continue

            await transport.send(response)
    except (KeyboardInterrupt, GracefulExit):
        click.echo("")
    finally:
        await transport.stop()


@click.command()
@click.option(
    "--model",
    type=str,
    default=None,
    help="Model override for the LLM (e.g., openrouter/openai/o3-mini)",
)
@click.option(
    "--max-tokens",
    type=int,
    default=None,
    help="Max tokens for LLM response (default from config)",
)
@click.option(
    "--no-system-prompt",
    is_flag=True,
    help="Disable the PPC Task Spec system prompt",
)
@click.option(
    "--transport",
    type=click.Choice(["cli", "telegram"]),
    default=None,
    help="Transport to use (default from config)",
)
def greeter(model: str | None, max_tokens: int | None, no_system_prompt: bool, transport: str | None) -> None:
    config = get_config()
    transport_name = transport or "cli"
    asyncio.run(run_greeter(config, transport_name, model, no_system_prompt, max_tokens))


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
