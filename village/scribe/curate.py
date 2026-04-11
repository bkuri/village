"""Curation engine for Scribe knowledge base.

Finds orphans, stale content, broken links, and missing cross-references.
Generates VOICE.md at project root.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from village.goals import Goal, parse_goals, write_goals
from village.memory import MemoryStore

logger = logging.getLogger(__name__)


@dataclass
class BrokenLink:
    entry_id: str
    url: str
    status_code: int | None
    error: str


@dataclass
class StaleEntry:
    entry_id: str
    title: str
    age_days: int


@dataclass
class CurateResult:
    broken_links: list[BrokenLink] = field(default_factory=list)
    orphans: list[str] = field(default_factory=list)
    stale_entries: list[StaleEntry] = field(default_factory=list)
    missing_links: list[dict[str, str | float]] = field(default_factory=list)
    voice_updated: bool = False
    goals_updated: bool = False
    total_entries: int = 0


class Curator:
    """Health checker and maintainer for the Scribe wiki."""

    def __init__(self, store: MemoryStore, wiki_path: Path, project_root: Path | None = None) -> None:
        self.store = store
        self.wiki_path = wiki_path
        self.project_root = project_root or wiki_path.parent

    def find_orphans(self) -> list[str]:
        """Find entries with no inbound references from other entries."""
        entries = self.store.all_entries()
        referenced_ids: set[str] = set()

        for entry in entries:
            related = entry.metadata.get("related", [])
            if isinstance(related, str):
                related = [related]
            for rid in related:
                referenced_ids.add(rid)

        orphans = []
        for entry in entries:
            if entry.id not in referenced_ids:
                orphans.append(entry.id)

        return orphans

    def find_stale(self, max_age_days: int = 90) -> list[StaleEntry]:
        """Find entries older than max_age_days."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=max_age_days)

        stale = []
        for entry in self.store.all_entries():
            if entry.created < cutoff:
                age_days = (now - entry.created).days
                stale.append(StaleEntry(entry_id=entry.id, title=entry.title, age_days=age_days))

        return stale

    def check_links(self) -> list[BrokenLink]:
        """HTTP HEAD check for URL sources in entries."""
        broken = []
        entries = self.store.all_entries()

        for entry in entries:
            source = entry.metadata.get("source", "")
            if not isinstance(source, str) or not source.startswith(("http://", "https://")):
                continue

            try:
                resp = httpx.head(source, timeout=10.0, follow_redirects=True)
                if resp.status_code >= 400:
                    broken.append(
                        BrokenLink(
                            entry_id=entry.id,
                            url=source,
                            status_code=resp.status_code,
                            error="",
                        )
                    )
            except httpx.HTTPError as e:
                broken.append(
                    BrokenLink(
                        entry_id=entry.id,
                        url=source,
                        status_code=None,
                        error=str(e),
                    )
                )

        return broken

    def generate_voice(self) -> bool:
        """Generate VOICE.md at project root from wiki content."""
        entries = self.store.all_entries()
        if not entries:
            return False

        entries_by_recency = sorted(entries, key=lambda e: e.created, reverse=True)

        lines: list[str] = []
        lines.append("# Village Voice")
        lines.append(f"> Last updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d')} by Village Scribe")
        lines.append("")

        lines.append("## Recent Activity")
        for entry in entries_by_recency[:5]:
            date_str = entry.created.strftime("%Y-%m-%d")
            lines.append(f"- [{date_str}] {entry.title} (see: {entry.id})")
        lines.append("")

        convention_entries = [e for e in entries if "convention" in [t.lower() for t in e.tags]]
        if convention_entries:
            lines.append("## Conventions")
            for entry in convention_entries[:10]:
                first_line = entry.text.split("\n")[0].strip() if entry.text else entry.title
                lines.append(f"- {first_line}")
            lines.append("")

        gotcha_tags = {"gotcha", "mistake", "blocker"}
        gotcha_entries = [e for e in entries if any(t.lower() in gotcha_tags for t in e.tags)]
        if gotcha_entries:
            lines.append("## Known Gotchas")
            for entry in gotcha_entries[:10]:
                first_line = entry.text.split("\n")[0].strip() if entry.text else entry.title
                lines.append(f"- {first_line}")
            lines.append("")

        lines.append("## Wiki Index")
        for entry in entries_by_recency:
            lines.append(f"- [{entry.id}] {entry.title}")
        lines.append("")

        voice_path = self.project_root / "VOICE.md"
        voice_path.write_text("\n".join(lines), encoding="utf-8")
        return True

    def bootstrap_goals(self) -> list[Goal]:
        """Scan wiki pages for implicit goals and return Goal objects."""
        entries = self.store.all_entries()
        if not entries:
            return []

        theme_tags: dict[str, list[str]] = {}
        for entry in entries:
            for tag in entry.tags:
                tag_lower = tag.lower()
                theme_tags.setdefault(tag_lower, []).append(entry.id)

        significant_themes = {
            tag: ids for tag, ids in theme_tags.items() if len(ids) >= 1 and tag not in {"synthesized", "query-result"}
        }

        goals: list[Goal] = []
        sorted_themes = sorted(significant_themes.items(), key=lambda x: len(x[1]), reverse=True)
        for idx, (theme, entry_ids) in enumerate(sorted_themes[:10], 1):
            goal_id = f"G{idx}"
            title = theme.replace("-", " ").replace("_", " ").title()
            description = f"Theme '{theme}' spanning {len(entry_ids)} wiki page(s)"
            goals.append(
                Goal(
                    id=goal_id,
                    title=title,
                    description=description,
                    status="active",
                    source=f"wiki:{','.join(entry_ids[:3])}",
                )
            )

        return goals

    def generate_goals(self) -> list[Goal]:
        """Generate goal hierarchy from wiki content and write GOALS.md."""
        goals_path = self.project_root / "GOALS.md"
        if goals_path.exists():
            existing = parse_goals(goals_path)
            if existing:
                return existing

        goals = self.bootstrap_goals()
        if goals:
            write_goals(goals, goals_path)
        return goals

    def curate(self, max_age_days: int = 90, check_urls: bool = True) -> CurateResult:
        """Run all health checks and regenerate VOICE.md."""
        result = CurateResult()
        result.total_entries = len(self.store.all_entries())
        result.orphans = self.find_orphans()
        result.stale_entries = self.find_stale(max_age_days)

        if check_urls:
            result.broken_links = self.check_links()

        result.voice_updated = self.generate_voice()

        goals = self.generate_goals()
        result.goals_updated = len(goals) > 0

        return result
