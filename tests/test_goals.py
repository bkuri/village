"""Tests for village/goals.py goal hierarchy."""

from pathlib import Path

import pytest

from village.elder.curate import Curator
from village.goals import (
    Goal,
    get_active_goals,
    get_goal_chain,
    get_objective_coverage,
    get_objective_coverage_from_file,
    parse_goals,
    write_goals,
)
from village.memory import MemoryStore

SAMPLE_GOALS_MD = """\
# Project Goals

## G1: Ship stable CLI orchestrator [active]

Build a reliable, CLI-native tool for parallel development.

### Objectives
- [x] Task state machine with persistence
- [x] Queue scheduler with concurrency limits
- [ ] Approval gates for high-risk tasks
- [ ] Structured audit trails

### Children
- G2

---

## G2: Knowledge management [active]

Self-improving documentation system.

### Objectives
- [x] Elder knowledge base
- [x] Cross-linking engine
- [x] VOICE.md generation
- [ ] Goal hierarchy integration

---

## G3: Completed milestone [completed]

Done and dusted.

### Objectives
- [x] First release
"""


@pytest.fixture
def goals_file(tmp_path: Path) -> Path:
    goals_path = tmp_path / "GOALS.md"
    goals_path.write_text(SAMPLE_GOALS_MD, encoding="utf-8")
    return goals_path


class TestParseGoals:
    def test_parse_valid_goals(self, goals_file: Path) -> None:
        goals = parse_goals(goals_file)
        assert len(goals) == 3

        g1 = goals[0]
        assert g1.id == "G1"
        assert g1.title == "Ship stable CLI orchestrator"
        assert g1.status == "active"
        assert "parallel development" in g1.description
        assert len(g1.objectives) == 2
        assert "Task state machine" in g1.objectives[0]
        assert "Queue scheduler" in g1.objectives[1]
        assert g1.children == ["G2"]
        assert g1.parent is None

    def test_parse_children_set_parent(self, goals_file: Path) -> None:
        goals = parse_goals(goals_file)
        g2 = [g for g in goals if g.id == "G2"][0]
        assert g2.parent == "G1"

    def test_parse_completed_goal(self, goals_file: Path) -> None:
        goals = parse_goals(goals_file)
        g3 = [g for g in goals if g.id == "G3"][0]
        assert g3.status == "completed"

    def test_parse_missing_file(self, tmp_path: Path) -> None:
        goals = parse_goals(tmp_path / "nonexistent.md")
        assert goals == []

    def test_parse_empty_file(self, tmp_path: Path) -> None:
        empty = tmp_path / "GOALS.md"
        empty.write_text("", encoding="utf-8")
        goals = parse_goals(empty)
        assert goals == []


class TestGetGoalChain:
    def test_chain_from_root_to_child(self, goals_file: Path) -> None:
        goals = parse_goals(goals_file)
        chain = get_goal_chain(goals, "G2")
        assert len(chain) == 2
        assert chain[0].id == "G1"
        assert chain[1].id == "G2"

    def test_chain_root_only(self, goals_file: Path) -> None:
        goals = parse_goals(goals_file)
        chain = get_goal_chain(goals, "G1")
        assert len(chain) == 1
        assert chain[0].id == "G1"

    def test_chain_unknown_goal(self, goals_file: Path) -> None:
        goals = parse_goals(goals_file)
        chain = get_goal_chain(goals, "G99")
        assert chain == []


class TestGetActiveGoals:
    def test_filter_active(self, goals_file: Path) -> None:
        goals = parse_goals(goals_file)
        active = get_active_goals(goals)
        assert len(active) == 2
        assert all(g.status == "active" for g in active)

    def test_all_completed(self, tmp_path: Path) -> None:
        goals_path = tmp_path / "GOALS.md"
        goals_path.write_text(
            "# Goals\n\n## G1: Done [completed]\n\nFinished.\n",
            encoding="utf-8",
        )
        goals = parse_goals(goals_path)
        active = get_active_goals(goals)
        assert active == []


class TestGetObjectiveCoverage:
    def test_coverage_calculation(self, goals_file: Path) -> None:
        goals = parse_goals(goals_file)
        coverage = get_objective_coverage(goals)
        assert coverage["G1"] == 1.0
        assert coverage["G2"] == 1.0
        assert coverage["G3"] == 1.0

    def test_coverage_no_objectives(self, tmp_path: Path) -> None:
        goals_path = tmp_path / "GOALS.md"
        goals_path.write_text(
            "# Goals\n\n## G1: No objs [active]\n\nNo objectives here.\n",
            encoding="utf-8",
        )
        goals = parse_goals(goals_path)
        coverage = get_objective_coverage(goals)
        assert coverage["G1"] == 0.0


class TestGetObjectiveCoverageFromFile:
    def test_raw_coverage(self, goals_file: Path) -> None:
        coverage = get_objective_coverage_from_file(goals_file)
        assert "G1" in coverage
        completed, total, ratio = coverage["G1"]
        assert completed == 2
        assert total == 4
        assert ratio == 0.5

        assert "G2" in coverage
        completed, total, ratio = coverage["G2"]
        assert completed == 3
        assert total == 4
        assert ratio == 0.75

    def test_raw_coverage_missing_file(self, tmp_path: Path) -> None:
        coverage = get_objective_coverage_from_file(tmp_path / "nope.md")
        assert coverage == {}


class TestWriteGoals:
    def test_round_trip(self, goals_file: Path, tmp_path: Path) -> None:
        goals = parse_goals(goals_file)
        raw = get_objective_coverage_from_file(goals_file)

        raw_obj: dict[str, tuple[list[str], list[str]]] = {}
        for gid, (_completed, _total, _ratio) in raw.items():
            all_objs = list(
                goals_file.read_text(encoding="utf-8")
                .split(f"## {gid}:")[1]
                .split("### Objectives")[1]
                .split("###")[0]
                .strip()
                .split("\n")
            )
            done = []
            not_done = []
            for line in all_objs:
                line = line.strip()
                if not line:
                    continue
                if line.startswith("- [x]"):
                    done.append(line[6:].strip())
                elif line.startswith("- [ ]"):
                    not_done.append(line[6:].strip())
            raw_obj[gid] = (done, not_done)

        out_path = tmp_path / "GOALS_OUT.md"
        write_goals(goals, out_path, raw_objectives=raw_obj)

        assert out_path.exists()
        content = out_path.read_text(encoding="utf-8")
        assert "## G1: Ship stable CLI orchestrator [active]" in content
        assert "## G2: Knowledge management [active]" in content
        assert "## G3: Completed milestone [completed]" in content

    def test_write_without_raw(self, tmp_path: Path) -> None:
        goals = [
            Goal(id="G1", title="Test Goal", description="A test", objectives=["Obj 1"]),
        ]
        out_path = tmp_path / "GOALS.md"
        write_goals(goals, out_path)
        content = out_path.read_text(encoding="utf-8")
        assert "- [x] Obj 1" in content

    def test_round_trip_preserves_objectives(self, tmp_path: Path) -> None:
        content = SAMPLE_GOALS_MD
        goals_path = tmp_path / "GOALS.md"
        goals_path.write_text(content, encoding="utf-8")

        goals = parse_goals(goals_path)
        raw_obj: dict[str, tuple[list[str], list[str]]] = {}
        for line in content.splitlines():
            pass

        from village.goals import _parse_objectives_raw

        raw_obj = _parse_objectives_raw(goals_path)

        out_path = tmp_path / "GOALS_rt.md"
        write_goals(goals, out_path, raw_objectives=raw_obj)
        out_content = out_path.read_text(encoding="utf-8")
        assert "- [x] Task state machine with persistence" in out_content
        assert "- [ ] Approval gates for high-risk tasks" in out_content
        assert "- [x] Elder knowledge base" in out_content
        assert "- [ ] Goal hierarchy integration" in out_content


class TestCuratorBootstrapGoals:
    def test_bootstrap_from_entries(self, tmp_path: Path) -> None:
        store_path = tmp_path / "wiki" / "pages"
        store_path.mkdir(parents=True)
        store = MemoryStore(store_path)

        store.put(
            title="Auth system design",
            text="Design for authentication",
            tags=["auth", "security"],
        )
        store.put(
            title="Auth implementation",
            text="Implementation notes",
            tags=["auth", "backend"],
        )

        curator = Curator(store=store, wiki_path=tmp_path / "wiki", project_root=tmp_path)
        goals = curator.bootstrap_goals()
        assert len(goals) > 0
        assert any(g.id.startswith("G") for g in goals)

    def test_bootstrap_empty_store(self, tmp_path: Path) -> None:
        store_path = tmp_path / "wiki" / "pages"
        store_path.mkdir(parents=True)
        store = MemoryStore(store_path)

        curator = Curator(store=store, wiki_path=tmp_path / "wiki", project_root=tmp_path)
        goals = curator.bootstrap_goals()
        assert goals == []

    def test_generate_goals_creates_file(self, tmp_path: Path) -> None:
        store_path = tmp_path / "wiki" / "pages"
        store_path.mkdir(parents=True)
        store = MemoryStore(store_path)
        store.put(title="Testing guide", text="How to test", tags=["testing"])

        curator = Curator(store=store, wiki_path=tmp_path / "wiki", project_root=tmp_path)
        goals = curator.generate_goals()
        assert len(goals) > 0

        goals_path = tmp_path / "GOALS.md"
        assert goals_path.exists()

    def test_generate_goals_returns_existing(self, tmp_path: Path) -> None:
        goals_path = tmp_path / "GOALS.md"
        goals_path.write_text(SAMPLE_GOALS_MD, encoding="utf-8")

        store_path = tmp_path / "wiki" / "pages"
        store_path.mkdir(parents=True)
        store = MemoryStore(store_path)

        curator = Curator(store=store, wiki_path=tmp_path / "wiki", project_root=tmp_path)
        goals = curator.generate_goals()
        assert len(goals) == 3
        assert goals[0].id == "G1"


class TestCLIGoalsCommand:
    @staticmethod
    def _init_git_repo(path: Path) -> None:
        import subprocess

        subprocess.run(["git", "init"], cwd=path, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=path, capture_output=True, check=True)
        (path / ".village").mkdir()
        (path / ".worktrees").mkdir()
        village_dir = path / ".village"
        (village_dir / "config").write_text("", encoding="utf-8")

    def test_goals_command_no_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from click.testing import CliRunner

        from village.cli.goals import goals

        self._init_git_repo(tmp_path)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(goals)
        assert result.exit_code == 0
        assert "No GOALS.md found" in result.output

    def test_goals_command_tree(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from click.testing import CliRunner

        from village.cli.goals import goals

        self._init_git_repo(tmp_path)
        goals_path = tmp_path / "GOALS.md"
        goals_path.write_text(SAMPLE_GOALS_MD, encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(goals)
        assert result.exit_code == 0
        assert "G1" in result.output
        assert "G2" in result.output

    def test_goals_command_coverage(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from click.testing import CliRunner

        from village.cli.goals import goals

        self._init_git_repo(tmp_path)
        goals_path = tmp_path / "GOALS.md"
        goals_path.write_text(SAMPLE_GOALS_MD, encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(goals, ["--coverage"])
        assert result.exit_code == 0
        assert "2/4" in result.output
        assert "Overall:" in result.output

    def test_goals_command_json(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import json

        from click.testing import CliRunner

        from village.cli.goals import goals

        self._init_git_repo(tmp_path)
        goals_path = tmp_path / "GOALS.md"
        goals_path.write_text(SAMPLE_GOALS_MD, encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(goals, ["--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 3
        assert data[0]["id"] == "G1"
