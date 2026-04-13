"""Polling-based file monitor for wiki/ingest/ directory."""

import asyncio
import json
import signal
import time
from pathlib import Path
from typing import Any

from village.scribe.store import ScribeStore


class Monitor:
    def __init__(
        self,
        wiki_path: Path,
        store: ScribeStore,
        poll_interval: int = 30,
        auto_research: bool = False,
    ) -> None:
        self.wiki_path = wiki_path
        self.store = store
        self.poll_interval = poll_interval
        self.auto_research = auto_research
        self._state_path = wiki_path.parent / ".village" / "monitor_state.json"
        self._running = False
        self._researcher: Any = None
        self._research_result: Any = None

    def set_researcher(self, researcher: Any) -> None:
        """Set the auto-researcher for gap-filling."""
        self._researcher = researcher

    def _load_seen(self) -> set[str]:
        if not self._state_path.exists():
            return set()
        try:
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
            return set(data.get("seen", []))
        except (json.JSONDecodeError, OSError):
            return set()

    def _save_seen(self, seen: set[str]) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(
            json.dumps({"seen": sorted(seen)}, indent=2),
            encoding="utf-8",
        )

    def poll(self) -> list[dict[str, str]]:
        ingest_dir = self.wiki_path / "ingest"
        if not ingest_dir.exists():
            return []

        seen = self._load_seen()
        current_files = set(f.name for f in ingest_dir.iterdir() if f.is_file())
        new_files = current_files - seen

        results = []
        for filename in sorted(new_files):
            file_path = ingest_dir / filename
            result = self.store.see(str(file_path))
            results.append(
                {
                    "file": filename,
                    "entry_id": result.entry_id,
                    "title": result.title,
                    "status": result.status,
                }
            )

        if new_files:
            seen.update(new_files)
            self._save_seen(seen)

        return results

    def start(self) -> None:
        self._running = True

        def _stop(signum: int, frame: object) -> None:
            self._running = False

        signal.signal(signal.SIGINT, _stop)
        signal.signal(signal.SIGTERM, _stop)

        while self._running:
            results = self.poll()
            for r in results:
                print(f"[{r['status']}] {r['file']} -> {r.get('title', r.get('entry_id', '?'))}")

            if self.auto_research and self._researcher and results:
                print("Running auto-research on new entries...")
                try:
                    research_result = asyncio.run(
                        self._researcher.research_gaps(max_orphans=3)
                    )
                    self._research_result = research_result
                    print(
                        f"Research complete: {research_result.gaps_researched} "
                        "gaps filled"
                    )
                except Exception as e:
                    print(f"Auto-research failed: {e}")

            time.sleep(self.poll_interval)

    def stop(self) -> None:
        self._running = False
