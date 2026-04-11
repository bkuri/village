"""Tests for Scribe cross-linking engine."""

from pathlib import Path

from village.memory import MemoryStore
from village.scribe.crosslink import (
    _tag_jaccard,
    _title_keyword_overlap,
    find_related,
    suggest_links,
    update_cross_references,
)


class TestTagJaccard:
    def test_identical_tags(self) -> None:
        score = _tag_jaccard(["auth", "env"], ["auth", "env"])
        assert score == 1.0

    def test_partial_overlap(self) -> None:
        score = _tag_jaccard(["auth", "env"], ["auth", "git"])
        assert score == 0.3333333333333333

    def test_no_overlap(self) -> None:
        score = _tag_jaccard(["auth"], ["git"])
        assert score == 0.0

    def test_empty_tags_a(self) -> None:
        score = _tag_jaccard([], ["auth"])
        assert score == 0.0

    def test_empty_tags_b(self) -> None:
        score = _tag_jaccard(["auth"], [])
        assert score == 0.0

    def test_both_empty(self) -> None:
        score = _tag_jaccard([], [])
        assert score == 0.0

    def test_case_insensitive(self) -> None:
        score = _tag_jaccard(["Auth", "Env"], ["auth", "env"])
        assert score == 1.0


class TestTitleKeywordOverlap:
    def test_identical_titles(self) -> None:
        score = _title_keyword_overlap("Auth setup guide", "Auth setup guide")
        assert score == 1.0

    def test_partial_overlap(self) -> None:
        score = _title_keyword_overlap("Auth setup guide", "Auth configuration guide")
        assert score > 0.0
        assert score < 1.0

    def test_no_overlap(self) -> None:
        score = _title_keyword_overlap("Auth setup", "Git hooks")
        assert score == 0.0

    def test_empty_title_a(self) -> None:
        score = _title_keyword_overlap("", "Auth setup")
        assert score == 0.0

    def test_empty_title_b(self) -> None:
        score = _title_keyword_overlap("Auth setup", "")
        assert score == 0.0

    def test_both_empty(self) -> None:
        score = _title_keyword_overlap("", "")
        assert score == 0.0

    def test_stop_words_ignored(self) -> None:
        score = _title_keyword_overlap("the auth setup", "auth setup")
        assert score == 1.0

    def test_case_insensitive(self) -> None:
        score = _title_keyword_overlap("Auth Setup", "auth setup")
        assert score == 1.0

    def test_only_stop_words(self) -> None:
        score = _title_keyword_overlap("the a an", "is are was")
        assert score == 0.0


class TestFindRelated:
    def test_tag_overlap(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        store.put(title="Auth setup", text="body", tags=["auth", "env", "configuration"], entry_id="a")
        store.put(title="Git setup", text="body", tags=["git", "env", "configuration"], entry_id="b")
        store.put(title="Cooking tips", text="body", tags=["food", "recipe"], entry_id="c")

        entry = store.get("a")
        assert entry is not None
        results = find_related(store, entry)

        ids = [r[0].id for r in results]
        assert "b" in ids
        assert "c" not in ids

    def test_title_overlap(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        store.put(title="Authentication setup guide", text="body", tags=["auth"], entry_id="a")
        store.put(title="Authentication configuration guide", text="body", tags=["git"], entry_id="b")
        store.put(title="Cooking tips", text="body", tags=["food"], entry_id="c")

        entry = store.get("a")
        assert entry is not None
        results = find_related(store, entry)

        ids = [r[0].id for r in results]
        assert "b" in ids
        assert "c" not in ids

    def test_no_related_entries(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        store.put(title="Auth setup", text="body", tags=["auth"], entry_id="a")
        store.put(title="Cooking tips", text="body", tags=["food"], entry_id="b")

        entry = store.get("a")
        assert entry is not None
        results = find_related(store, entry)
        assert results == []

    def test_score_threshold(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        store.put(title="Auth setup", text="body", tags=["auth"], entry_id="a")
        store.put(title="Completely unrelated topic", text="body", tags=["unrelated"], entry_id="b")

        entry = store.get("a")
        assert entry is not None
        results = find_related(store, entry)
        assert results == []

    def test_respects_k_limit(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        store.put(title="Auth setup", text="body", tags=["auth", "env"], entry_id="a")
        store.put(title="Auth config", text="body", tags=["auth", "env"], entry_id="b")
        store.put(title="Auth guide", text="body", tags=["auth", "env"], entry_id="c")
        store.put(title="Auth reference", text="body", tags=["auth", "env"], entry_id="d")

        entry = store.get("a")
        assert entry is not None
        results = find_related(store, entry, k=2)
        assert len(results) == 2

    def test_sorted_by_score_descending(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        store.put(title="Auth setup", text="body", tags=["auth", "env", "config"], entry_id="a")
        store.put(title="Auth env config", text="body", tags=["auth", "env", "config"], entry_id="b")
        store.put(title="Auth only", text="body", tags=["auth"], entry_id="c")

        entry = store.get("a")
        assert entry is not None
        results = find_related(store, entry)

        scores = [r[1] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_excludes_self(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        store.put(title="Auth setup", text="body", tags=["auth"], entry_id="a")

        entry = store.get("a")
        assert entry is not None
        results = find_related(store, entry)
        assert results == []


class TestUpdateCrossReferences:
    def test_bidirectional_linking(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        store.put(title="Auth setup", text="body", tags=["auth"], entry_id="a")
        store.put(title="Git setup", text="body", tags=["git"], entry_id="b")

        updated = update_cross_references(store, "a", ["b"])
        assert updated == 2

        source = store.get("a")
        target = store.get("b")
        assert source is not None
        assert target is not None
        assert "b" in source.metadata["related"]
        assert "a" in target.metadata["related"]

    def test_skips_already_linked(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        store.put(title="Auth setup", text="body", tags=["auth"], metadata={"related": ["b"]}, entry_id="a")
        store.put(title="Git setup", text="body", tags=["git"], metadata={"related": ["a"]}, entry_id="b")

        updated = update_cross_references(store, "a", ["b"])
        assert updated == 0

    def test_source_not_found(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        updated = update_cross_references(store, "nonexistent", ["b"])
        assert updated == 0

    def test_target_not_found(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        store.put(title="Auth setup", text="body", tags=["auth"], entry_id="a")

        updated = update_cross_references(store, "a", ["nonexistent"])
        assert updated == 0

    def test_multiple_related(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        store.put(title="Auth setup", text="body", tags=["auth"], entry_id="a")
        store.put(title="Git setup", text="body", tags=["git"], entry_id="b")
        store.put(title="Env setup", text="body", tags=["env"], entry_id="c")

        updated = update_cross_references(store, "a", ["b", "c"])
        assert updated == 3

        source = store.get("a")
        assert source is not None
        related = source.metadata["related"]
        assert "b" in related
        assert "c" in related

    def test_preserves_existing_metadata(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        store.put(title="Auth setup", text="body", tags=["auth"], metadata={"source": "docs"}, entry_id="a")
        store.put(title="Git setup", text="body", tags=["git"], entry_id="b")

        update_cross_references(store, "a", ["b"])

        source = store.get("a")
        assert source is not None
        assert source.metadata.get("source") == "docs"
        assert "b" in source.metadata["related"]


class TestSuggestLinks:
    def test_finds_missing_connections(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        store.put(title="Auth setup", text="body", tags=["auth", "env", "configuration"], entry_id="a")
        store.put(title="Git setup", text="body", tags=["git", "env", "configuration"], entry_id="b")
        store.put(title="Cooking tips", text="body", tags=["food", "recipe"], entry_id="c")

        suggestions = suggest_links(store)
        assert len(suggestions) >= 1

        pair_ids = {(s.source_id, s.target_id) for s in suggestions}
        assert ("a", "b") in pair_ids

    def test_skips_already_linked_pairs(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        store.put(
            title="Auth setup",
            text="body",
            tags=["auth", "env", "configuration"],
            metadata={"related": ["b"]},
            entry_id="a",
        )
        store.put(
            title="Git setup",
            text="body",
            tags=["git", "env", "configuration"],
            metadata={"related": ["a"]},
            entry_id="b",
        )

        suggestions = suggest_links(store)
        pair_ids = {(s.source_id, s.target_id) for s in suggestions}
        assert ("a", "b") not in pair_ids

    def test_low_tag_overlap_filtered(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        store.put(title="Auth setup", text="body", tags=["auth", "env"], entry_id="a")
        store.put(title="Git tips", text="body", tags=["git", "tips"], entry_id="b")

        suggestions = suggest_links(store)
        assert len(suggestions) == 0

    def test_sorted_by_score_descending(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        store.put(title="A", text="body", tags=["x", "y", "z"], entry_id="a")
        store.put(title="B", text="body", tags=["x", "y", "z"], entry_id="b")
        store.put(title="C", text="body", tags=["x"], entry_id="c")

        suggestions = suggest_links(store)
        scores = [s.score for s in suggestions]
        assert scores == sorted(scores, reverse=True)

    def test_empty_store(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        suggestions = suggest_links(store)
        assert suggestions == []

    def test_single_entry(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        store.put(title="Auth setup", text="body", tags=["auth"], entry_id="a")
        suggestions = suggest_links(store)
        assert suggestions == []
