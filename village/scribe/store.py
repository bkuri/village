import logging
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import trafilatura

from village.memory import MemoryStore

logger = logging.getLogger(__name__)

MAX_DISTILL_SIZE = 2000

STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "is",
        "it",
        "as",
        "be",
        "was",
        "are",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "shall",
        "can",
        "not",
        "this",
        "that",
        "these",
        "those",
        "i",
        "you",
        "he",
        "she",
        "we",
        "they",
        "me",
        "him",
        "her",
        "us",
        "them",
        "my",
        "your",
        "his",
        "its",
        "our",
        "their",
        "what",
        "which",
        "who",
        "whom",
        "how",
        "when",
        "where",
        "why",
        "all",
        "each",
        "every",
        "both",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "no",
        "nor",
        "too",
        "very",
        "just",
        "about",
        "above",
        "after",
        "before",
        "between",
        "into",
        "through",
        "during",
        "up",
        "down",
        "out",
        "off",
        "over",
        "under",
        "then",
        "once",
        "here",
        "there",
        "if",
        "so",
        "than",
    }
)


@dataclass
class IngestResult:
    entry_id: str
    title: str
    tags: list[str] = field(default_factory=list)
    status: str = "success"
    error: str = ""


@dataclass
class AskResult:
    answer: str
    sources: list[str]
    saved: bool


class ScribeStore:
    def __init__(self, wiki_path: Path) -> None:
        self.wiki_path = wiki_path
        self.ingest_dir = wiki_path / "ingest"
        self.processed_dir = wiki_path / "processed"
        self.pages_dir = wiki_path / "pages"
        self.log_path = wiki_path / "log.md"
        self.store = MemoryStore(wiki_path / "pages")

    def _ensure_dirs(self) -> None:
        self.ingest_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.pages_dir.mkdir(parents=True, exist_ok=True)

    def _extract_url(self, url: str) -> tuple[str, str]:
        response = httpx.get(url, timeout=30.0, follow_redirects=True)
        response.raise_for_status()
        html = response.text
        downloaded = trafilatura.bare_extraction(html, url=url)
        if downloaded is None:
            return url, html
        if isinstance(downloaded, dict):
            title = downloaded.get("title") or url
            text = downloaded.get("text") or ""
        else:
            title = getattr(downloaded, "title", None) or url
            text = getattr(downloaded, "text", None) or ""
        return title, text

    def _distill(self, text: str, title: str) -> str:
        if len(text) <= MAX_DISTILL_SIZE:
            return text

        try:
            from village.config import get_config
            from village.llm.factory import get_llm_client

            config = get_config()
            llm = get_llm_client(config)
            prompt = (
                f"Distill the following document into a concise summary of actionable knowledge. "
                f"Extract key conventions, patterns, rules, and important facts. "
                f"Document title: {title}\n\n{text}"
            )
            system_prompt = (
                "You are a knowledge distillation assistant. Produce a concise summary "
                "that preserves actionable information, conventions, and key patterns. "
                "Do not include preamble — output only the distilled content."
            )
            result = llm.call(prompt, system_prompt=system_prompt, max_tokens=2048, timeout=60)
            return result.strip()
        except Exception:
            logger.warning("LLM distillation failed, falling back to truncation", exc_info=True)
            return f"{text[:MAX_DISTILL_SIZE]}\n\n[Content truncated — original was {len(text)} chars]"

    def _extract_file(self, path: Path, raw: bool = False) -> tuple[str, str]:
        text = path.read_text(encoding="utf-8")
        title = path.stem
        if not raw:
            text = self._distill(text, title)
        return title, text

    def _extract(self, source: str, raw: bool = False) -> tuple[str, str]:
        if source.startswith("http://") or source.startswith("https://"):
            return self._extract_url(source)
        path = Path(source)
        if path.exists():
            return self._extract_file(path, raw=raw)
        raise FileNotFoundError(f"Source not found: {source}")

    def _append_log(self, source: str, entry_id: str, title: str) -> None:
        if self.log_path.exists():
            existing = self.log_path.read_text(encoding="utf-8")
        else:
            existing = "# Ingest Log\n\n"
        line = f"- [{entry_id}] {title} — _{source}_\n"
        self.log_path.write_text(existing + line, encoding="utf-8")

    def _generate_tags(self, title: str) -> list[str]:
        words = title.lower().split()
        return [w for w in words if w not in STOP_WORDS and len(w) > 1]

    def see(self, source: str, raw: bool = False) -> IngestResult:
        self._ensure_dirs()
        try:
            title, text = self._extract(source, raw=raw)
        except Exception as exc:
            return IngestResult(
                entry_id="",
                title="",
                tags=[],
                status="error",
                error=str(exc),
            )

        tags = self._generate_tags(title)
        entry_id = self.store.put(
            title,
            text,
            tags=tags,
            metadata={"source": source},
        )
        self._append_log(source, entry_id, title)

        source_path = Path(source)
        if not source.startswith("http") and source_path.exists():
            try:
                ingest_file = self.ingest_dir / source_path.name
                if ingest_file.exists():
                    processed_file = self.processed_dir / source_path.name
                    ingest_file.rename(processed_file)
            except OSError:
                pass

        return IngestResult(
            entry_id=entry_id,
            title=title,
            tags=tags,
            status="success",
            error="",
        )

    def ask(self, question: str, save: bool = False) -> AskResult:
        """Query wiki and synthesize an answer."""
        hits = self.store.find(question, k=5)

        if not hits:
            return AskResult(answer="No relevant pages found.", sources=[], saved=False)

        context_parts = []
        source_ids = []
        for hit in hits:
            context_parts.append(f"[{hit.id}] {hit.title}\n{hit.text}")
            source_ids.append(hit.id)

        answer = "\n\n".join(context_parts)

        saved = False
        if save and answer:
            tags = ["synthesized", "query-result"]
            self.store.put(
                title=f"Q: {question[:80]}",
                text=answer,
                tags=tags,
                metadata={"synthesized_from": source_ids},
            )
            saved = True

        return AskResult(answer=answer, sources=source_ids, saved=saved)
