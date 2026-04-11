"""Council CLI commands -- multi-persona deliberation."""

import json
from pathlib import Path
from typing import Optional

import click

from village.config import CouncilConfig, get_config
from village.council.engine import CouncilEngine
from village.roles import run_role_chat


def _find_wiki_path() -> Path:
    cwd = Path.cwd()
    current = cwd
    while current != current.parent:
        if (current / ".git").exists():
            return current / "wiki"
        current = current.parent
    return cwd / "wiki"


def _get_engine(config: CouncilConfig) -> CouncilEngine:
    wiki_path = _find_wiki_path()
    personas_dir = Path(config.personas_dir)
    if not personas_dir.is_absolute():
        personas_dir = Path.cwd() / personas_dir
    return CouncilEngine(config=config, personas_dir=personas_dir, wiki_dir=wiki_path)


@click.group(invoke_without_command=True)
@click.pass_context
def council_group(
    ctx: click.Context,
) -> None:
    """Multi-persona deliberation system."""
    if ctx.invoked_subcommand is not None:
        return

    run_role_chat("council")


@council_group.command("list")
@click.option("--type", "meeting_type", type=click.Choice(["chat", "debate"]), help="Filter by type")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def list_councils(meeting_type: Optional[str], json_output: bool) -> None:
    """List past councils."""
    wiki_path = _find_wiki_path()
    councils_dir = wiki_path / "councils"

    if not councils_dir.exists():
        if json_output:
            click.echo("[]")
        else:
            click.echo("No councils found.")
        return

    entries: list[dict[str, str]] = []
    for council_dir in sorted(councils_dir.iterdir()):
        if not council_dir.is_dir():
            continue
        transcript_path = council_dir / "transcript.md"
        if not transcript_path.exists():
            continue

        content = transcript_path.read_text(encoding="utf-8")
        entry: dict[str, str] = {"council_id": council_dir.name}

        for line in content.split("\n"):
            if line.startswith("- **Type**:"):
                entry["meeting_type"] = line.split(":", 1)[1].strip()
            elif line.startswith("- **Topic**:"):
                entry["topic"] = line.split(":", 1)[1].strip()
            elif line.startswith("- **Created**:"):
                entry["created"] = line.split(":", 1)[1].strip()

        if meeting_type and entry.get("meeting_type") != meeting_type:
            continue

        entries.append(entry)

    if json_output:
        click.echo(json.dumps(entries, indent=2))
    else:
        if not entries:
            click.echo("No councils found.")
            return
        for entry in entries:
            click.echo(f"  {entry['council_id']}  {entry.get('meeting_type', '?')}  {entry.get('topic', '?')[:60]}")


@council_group.command()
@click.argument("council_id")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def show(council_id: str, json_output: bool) -> None:
    """Show a council transcript."""
    wiki_path = _find_wiki_path()
    transcript_path = wiki_path / "councils" / council_id / "transcript.md"

    if not transcript_path.exists():
        click.echo(f"Council not found: {council_id}")
        raise SystemExit(1)

    content = transcript_path.read_text(encoding="utf-8")

    if json_output:
        lines = content.split("\n")
        metadata: dict[str, str] = {}
        turns: list[dict[str, str]] = []
        current_persona = ""

        for line in lines:
            if line.startswith("- **"):
                key_end = line.index("**:", 3)
                key = line[3:key_end].lower().replace(" ", "_")
                metadata[key] = line[key_end + 3 :].strip()
            elif line.startswith("## Turn"):
                parts = line.split(":", 1)
                if len(parts) > 1:
                    current_persona = parts[1].split("[")[0].strip()
            elif line.strip() and current_persona and not line.startswith("#") and not line.startswith("---"):
                turns.append({"persona": current_persona, "content": line.strip()})

        click.echo(json.dumps({"metadata": metadata, "turns": turns}, indent=2))
    else:
        click.echo(content)


@council_group.command()
@click.argument("council_id")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def rematch(council_id: str, json_output: bool) -> None:
    """Re-run a council with the same configuration."""
    wiki_path = _find_wiki_path()
    transcript_path = wiki_path / "councils" / council_id / "transcript.md"

    if not transcript_path.exists():
        click.echo(f"Council not found: {council_id}")
        raise SystemExit(1)

    content = transcript_path.read_text(encoding="utf-8")

    topic = ""
    meeting_type = "chat"
    found_personas: list[str] = []

    for line in content.split("\n"):
        if line.startswith("- **Topic**:"):
            topic = line.split(":", 1)[1].strip()
        elif line.startswith("- **Type**:"):
            meeting_type = line.split(":", 1)[1].strip()
        elif line.startswith("## Turn"):
            parts = line.split(":", 1)
            if len(parts) > 1:
                name = parts[1].split("[")[0].strip()
                if name not in found_personas:
                    found_personas.append(name)

    if not topic:
        click.echo("Could not extract topic from transcript.")
        raise SystemExit(1)

    config = get_config()
    engine = _get_engine(config.council)

    state = engine.start_meeting(
        topic=topic,
        meeting_type=meeting_type,
        persona_names=found_personas or None,
    )

    click.echo(f"Rematch: {state.council_id} (from {council_id})")
    click.echo(f"  Topic: {state.topic}")
    click.echo(f"  Personas: {', '.join(p.name for p in state.personas)}")

    for round_num in range(state.max_rounds):
        turns = engine.run_round(state)
        if not turns:
            break

        for turn in turns:
            click.echo(f"\n  [{turn.persona_name}]: {turn.content[:200]}")

    resolution = engine.resolve(state)
    click.echo(f"\nResolution: {resolution.summary[:300]}")

    path = engine.save_and_close(state)
    if path:
        click.echo(f"\nTranscript saved: {path}")

    if json_output:
        output = {
            "council_id": state.council_id,
            "original_id": council_id,
            "topic": state.topic,
            "meeting_type": state.meeting_type,
            "status": state.status,
        }
        click.echo(json.dumps(output, indent=2))


@council_group.command()
@click.argument("topic")
@click.option("--type", "meeting_type", type=click.Choice(["chat", "debate"]), default="debate", help="Meeting type")
@click.option("--personas", type=str, help="Comma-separated persona names")
@click.option("--rounds", type=int, help="Number of rounds")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def debate(
    topic: str,
    meeting_type: str,
    personas: Optional[str],
    rounds: Optional[int],
    json_output: bool,
) -> None:
    """Start a council debate on a topic."""
    config = get_config()
    engine = _get_engine(config.council)

    persona_names: Optional[list[str]] = None
    if personas:
        persona_names = [p.strip() for p in personas.split(",") if p.strip()]

    state = engine.start_meeting(
        topic=topic,
        meeting_type=meeting_type,
        persona_names=persona_names,
    )

    if rounds is not None:
        state.max_rounds = rounds

    click.echo(f"Council: {state.council_id}")
    click.echo(f"  Topic: {state.topic}")
    click.echo(f"  Personas: {', '.join(p.name for p in state.personas)}")

    for _ in range(state.max_rounds):
        turns = engine.run_round(state)
        if not turns:
            break

        for turn in turns:
            click.echo(f"\n  [{turn.persona_name}]: {turn.content[:200]}")

    resolution = engine.resolve(state)
    click.echo(f"\nResolution: {resolution.summary[:300]}")

    path = engine.save_and_close(state)
    if path:
        click.echo(f"\nTranscript saved: {path}")

    if json_output:
        output = {
            "council_id": state.council_id,
            "topic": state.topic,
            "meeting_type": state.meeting_type,
            "status": state.status,
        }
        click.echo(json.dumps(output, indent=2))
