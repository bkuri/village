from pathlib import Path
from unittest.mock import patch

import pytest

from village.tasks.ids import (
    ID_LENGTH,
    ID_PREFIX,
    collect_existing_ids,
    extract_task_id_from_output,
    generate_task_id,
    validate_task_id,
)


class TestGenerateTaskId:
    def test_returns_valid_format(self):
        result = generate_task_id(set())
        assert result.startswith(f"{ID_PREFIX}-")
        assert len(result) == len(ID_PREFIX) + 1 + ID_LENGTH

    def test_unique_with_empty_set(self):
        result = generate_task_id(set())
        assert result not in set()

    def test_avoids_existing_ids(self):
        existing = {"bd-aabb", "bd-ccdd"}
        result = generate_task_id(existing)
        assert result not in existing

    def test_collision_handling(self):
        existing = set()
        ids = []
        for _ in range(50):
            tid = generate_task_id(existing)
            assert tid not in existing
            existing.add(tid)
            ids.append(tid)

        assert len(ids) == len(set(ids))

    def test_exhausted_retries_raises(self):
        from village.tasks.ids import ID_LENGTH

        existing = set()
        base_hex = "aabbccdd"
        existing.add(f"{ID_PREFIX}-{base_hex[:ID_LENGTH]}")
        for length in range(ID_LENGTH + 1, ID_LENGTH + 8):
            hex_part = base_hex[:length]
            existing.add(f"{ID_PREFIX}-{hex_part}")

        with patch("village.tasks.ids.secrets.token_hex", return_value=base_hex):
            with pytest.raises(RuntimeError, match="Failed to generate unique task ID"):
                generate_task_id(existing)


class TestCollectExistingIds:
    def test_nonexistent_file(self, tmp_path: Path):
        result = collect_existing_ids(tmp_path / "missing.jsonl")
        assert result == set()

    def test_empty_file(self, tmp_path: Path):
        f = tmp_path / "tasks.jsonl"
        f.write_text("", encoding="utf-8")
        assert collect_existing_ids(f) == set()

    def test_valid_entries(self, tmp_path: Path):
        f = tmp_path / "tasks.jsonl"
        f.write_text('{"id":"bd-a1b2","title":"A"}\n{"id":"bd-c3d4","title":"B"}\n', encoding="utf-8")
        result = collect_existing_ids(f)
        assert result == {"bd-a1b2", "bd-c3d4"}

    def test_skips_blank_lines(self, tmp_path: Path):
        f = tmp_path / "tasks.jsonl"
        f.write_text('{"id":"bd-a1b2","title":"A"}\n\n{"id":"bd-c3d4","title":"B"}\n', encoding="utf-8")
        result = collect_existing_ids(f)
        assert result == {"bd-a1b2", "bd-c3d4"}

    def test_skips_invalid_json(self, tmp_path: Path):
        f = tmp_path / "tasks.jsonl"
        f.write_text('{"id":"bd-a1b2","title":"A"}\nnot json\n{"id":"bd-c3d4","title":"B"}\n', encoding="utf-8")
        result = collect_existing_ids(f)
        assert result == {"bd-a1b2", "bd-c3d4"}

    def test_skips_entries_without_id(self, tmp_path: Path):
        f = tmp_path / "tasks.jsonl"
        f.write_text('{"id":"bd-a1b2","title":"A"}\n{"title":"No ID"}\n', encoding="utf-8")
        result = collect_existing_ids(f)
        assert result == {"bd-a1b2"}


class TestValidateTaskId:
    def test_valid(self):
        assert validate_task_id("bd-a3f8") is True

    def test_valid_longer(self):
        assert validate_task_id("bd-a3f8c1d2") is True

    def test_invalid_prefix(self):
        assert validate_task_id("xx-a3f8") is False

    def test_too_short(self):
        assert validate_task_id("bd-ab") is False

    def test_empty(self):
        assert validate_task_id("") is False

    def test_uppercase_accepted(self):
        assert validate_task_id("BD-A3F8") is True


class TestExtractTaskIdFromOutput:
    def test_exact_pattern(self):
        result = extract_task_id_from_output("Created task bd-a3f8 successfully")
        assert result == "bd-a3f8"

    def test_created_pattern(self):
        result = extract_task_id_from_output("created: bd-1234abcd")
        assert result == "bd-1234abcd"

    def test_task_id_pattern(self):
        result = extract_task_id_from_output("task id: BD-ABCD")
        assert result == "bd-abcd"

    def test_id_pattern(self):
        result = extract_task_id_from_output("id: bd-ff00")
        assert result == "bd-ff00"

    def test_no_match(self):
        assert extract_task_id_from_output("no task id here") is None

    def test_empty_string(self):
        assert extract_task_id_from_output("") is None

    def test_returns_lowercase(self):
        result = extract_task_id_from_output("Created BD-A3F8")
        assert result == "bd-a3f8"
