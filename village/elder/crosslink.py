"""Cross-linking engine for Elder knowledge base."""

from dataclasses import dataclass

from village.memory import MemoryEntry, MemoryStore


@dataclass
class MissingLink:
    source_id: str
    target_id: str
    score: float


def _tag_jaccard(tags_a: list[str], tags_b: list[str]) -> float:
    """Jaccard similarity between two tag sets."""
    set_a = set(t.lower() for t in tags_a)
    set_b = set(t.lower() for t in tags_b)
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


def _title_keyword_overlap(title_a: str, title_b: str) -> float:
    """Fraction of shared non-stopword tokens between two titles."""
    stop_words = {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "and",
        "or",
        "with",
    }
    tokens_a = set(title_a.lower().split()) - stop_words
    tokens_b = set(title_b.lower().split()) - stop_words
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def find_related(
    store: MemoryStore,
    entry: MemoryEntry,
    k: int = 5,
) -> list[tuple[MemoryEntry, float]]:
    """Find entries related to the given entry by tag overlap and title similarity.

    Returns list of (entry, score) tuples, sorted by score descending.
    Score = tag_jaccard * 0.6 + title_keyword_overlap * 0.4
    Filters out entries with score < 0.2
    """
    results: list[tuple[float, MemoryEntry]] = []
    for candidate in store.all_entries():
        if candidate.id == entry.id:
            continue
        tag_score = _tag_jaccard(entry.tags, candidate.tags)
        title_score = _title_keyword_overlap(entry.title, candidate.title)
        total = tag_score * 0.6 + title_score * 0.4
        if total >= 0.2:
            results.append((total, candidate))

    results.sort(key=lambda x: x[0], reverse=True)
    return [(entry, score) for score, entry in results[:k]]


def update_cross_references(
    store: MemoryStore,
    source_id: str,
    related_ids: list[str],
) -> int:
    """Add bidirectional cross-references between source and related entries.

    Updates the 'related' metadata field in frontmatter.

    Returns count of pages updated.
    """
    source = store.get(source_id)
    if source is None:
        return 0

    updated = 0
    existing_related: list[str] = source.metadata.get("related", [])  # type: ignore[assignment]
    if isinstance(existing_related, str):
        existing_related = [existing_related]
    existing_set = set(existing_related)

    for rid in related_ids:
        if rid in existing_set:
            continue
        existing_related.append(rid)

        target = store.get(rid)
        if target is None:
            continue

        target_related: list[str] = target.metadata.get("related", [])  # type: ignore[assignment]
        if isinstance(target_related, str):
            target_related = [target_related]
        if source_id not in target_related:
            target_related.append(source_id)

        store.delete(rid)
        store.put(
            title=target.title,
            text=target.text,
            tags=target.tags,
            metadata={**target.metadata, "related": target_related},
            entry_id=rid,
        )
        updated += 1

    if updated > 0:
        store.delete(source_id)
        store.put(
            title=source.title,
            text=source.text,
            tags=source.tags,
            metadata={**source.metadata, "related": existing_related},
            entry_id=source_id,
        )
        updated += 1

    return updated


def suggest_links(store: MemoryStore) -> list[MissingLink]:
    """Find page pairs that share tags but lack cross-references.

    Returns list of MissingLink suggestions sorted by score.
    """
    entries = store.all_entries()
    suggestions: list[MissingLink] = []

    for i, entry_a in enumerate(entries):
        for entry_b in entries[i + 1 :]:
            tag_score = _tag_jaccard(entry_a.tags, entry_b.tags)
            if tag_score < 0.3:
                continue

            related_a: list[str] = entry_a.metadata.get("related", [])  # type: ignore[assignment]
            related_b: list[str] = entry_b.metadata.get("related", [])  # type: ignore[assignment]
            if isinstance(related_a, str):
                related_a = [related_a]
            if isinstance(related_b, str):
                related_b = [related_b]

            if entry_b.id in related_a or entry_a.id in related_b:
                continue

            suggestions.append(
                MissingLink(
                    source_id=entry_a.id,
                    target_id=entry_b.id,
                    score=tag_score,
                )
            )

    suggestions.sort(key=lambda x: x.score, reverse=True)
    return suggestions
