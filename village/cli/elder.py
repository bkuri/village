"""Village Elder — self-improving knowledge base CLI commands."""

import json
from pathlib import Path

import click

from village.elder.curate import Curator
from village.elder.store import ElderStore


def _find_wiki_path() -> Path:
    cwd = Path.cwd()
    current = cwd
    while current != current.parent:
        if (current / ".git").exists():
            return current / "wiki"
        current = current.parent
    return cwd / "wiki"


@click.group()
def elder_group() -> None:
    """Manage project knowledge base."""


@elder_group.command()
@click.argument("source")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def see(source: str, as_json: bool) -> None:
    """Ingest a URL or file into the knowledge base."""
    wiki_path = _find_wiki_path()
    store = ElderStore(wiki_path)

    result = store.see(source)

    if as_json:
        click.echo(
            json.dumps(
                {
                    "entry_id": result.entry_id,
                    "title": result.title,
                    "tags": result.tags,
                    "status": result.status,
                }
            )
        )
    else:
        if result.status == "error":
            click.echo(f"Error: {result.error}")
            raise SystemExit(1)
        click.echo(f"Ingested: {result.title} ({result.entry_id})")
        if result.tags:
            click.echo(f"  Tags: {', '.join(result.tags)}")


@elder_group.command()
@click.argument("source")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def fetch(source: str, as_json: bool) -> None:
    """Ingest a URL or file into the knowledge base. (Alias for see)"""
    wiki_path = _find_wiki_path()
    store = ElderStore(wiki_path)

    result = store.see(source)

    if as_json:
        click.echo(
            json.dumps(
                {
                    "entry_id": result.entry_id,
                    "title": result.title,
                    "tags": result.tags,
                    "status": result.status,
                }
            )
        )
    else:
        if result.status == "error":
            click.echo(f"Error: {result.error}")
            raise SystemExit(1)
        click.echo(f"Ingested: {result.title} ({result.entry_id})")
        if result.tags:
            click.echo(f"  Tags: {', '.join(result.tags)}")


@elder_group.command()
@click.argument("question")
@click.option("--save", is_flag=True, help="Save answer as new wiki page")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def ask(question: str, save: bool, as_json: bool) -> None:
    """Query the knowledge base and synthesize an answer."""
    wiki_path = _find_wiki_path()
    store = ElderStore(wiki_path)

    result = store.ask(question, save=save)

    if as_json:
        click.echo(
            json.dumps(
                {
                    "answer": result.answer,
                    "sources": result.sources,
                    "saved": result.saved,
                }
            )
        )
    else:
        click.echo(result.answer)
        if result.sources:
            click.echo(f"\nSources: {', '.join(result.sources)}")


@elder_group.command()
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def curate(as_json: bool) -> None:
    """Health check and maintain the knowledge base."""
    wiki_path = _find_wiki_path()
    project_root = wiki_path.parent
    store = ElderStore(wiki_path)
    curator = Curator(store.store, wiki_path, project_root)

    result = curator.curate()

    if as_json:
        click.echo(
            json.dumps(
                {
                    "total_entries": result.total_entries,
                    "orphans": result.orphans,
                    "stale_count": len(result.stale_entries),
                    "broken_links": len(result.broken_links),
                    "voice_updated": result.voice_updated,
                }
            )
        )
    else:
        click.echo(f"Entries: {result.total_entries}")
        click.echo(f"Orphans: {len(result.orphans)}")
        if result.orphans:
            for oid in result.orphans:
                click.echo(f"  - {oid}")
        click.echo(f"Stale: {len(result.stale_entries)}")
        click.echo(f"Broken links: {len(result.broken_links)}")
        if result.broken_links:
            for bl in result.broken_links:
                click.echo(f"  - {bl.url} ({bl.status_code or 'error'})")
        click.echo(f"VOICE.md updated: {result.voice_updated}")


@elder_group.command()
def upkeep() -> None:
    """Health check and maintain the knowledge base. (Alias for curate)"""
    wiki_path = _find_wiki_path()
    project_root = wiki_path.parent
    store = ElderStore(wiki_path)
    curator = Curator(store.store, wiki_path, project_root)

    result = curator.curate()

    click.echo(f"Entries: {result.total_entries}")
    click.echo(f"Orphans: {len(result.orphans)}")
    click.echo(f"Stale: {len(result.stale_entries)}")
    click.echo(f"Broken links: {len(result.broken_links)}")
    click.echo(f"VOICE.md updated: {result.voice_updated}")


@elder_group.command()
def stats() -> None:
    """Show knowledge base statistics."""
    wiki_path = _find_wiki_path()
    store = ElderStore(wiki_path)

    entries = store.store.all_entries()
    log_path = wiki_path / "log.md"

    click.echo(f"Wiki path: {wiki_path}")
    click.echo(f"Total entries: {len(entries)}")

    if entries:
        all_tags: list[str] = []
        for e in entries:
            all_tags.extend(e.tags)
        unique_tags = set(all_tags)
        click.echo(f"Unique tags: {len(unique_tags)}")
        if unique_tags:
            click.echo(f"  Top tags: {', '.join(sorted(unique_tags)[:10])}")

        click.echo(f"Latest entry: {entries[-1].title} ({entries[-1].id})")

    if log_path.exists():
        log_content = log_path.read_text(encoding="utf-8")
        log_lines = [line for line in log_content.split("\n") if line.startswith("- [")]
        click.echo(f"Log entries: {len(log_lines)}")


@elder_group.command()
@click.option("--interval", default=30, help="Poll interval in seconds")
def monitor(interval: int) -> None:
    """Watch wiki/ingest/ for new files and process them."""
    from village.elder.monitor import Monitor

    wiki_path = _find_wiki_path()
    store = ElderStore(wiki_path)
    mon = Monitor(wiki_path, store, poll_interval=interval)

    click.echo(f"Monitoring {wiki_path / 'ingest'} every {interval}s (Ctrl+C to stop)")
    mon.start()
