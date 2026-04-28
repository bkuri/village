from pathlib import Path
from unittest.mock import MagicMock, patch

from village.contracts import _build_goal_context, generate_spec_contract
from village.goals import Goal

PPC_SPEC_OUTPUT = "# PPC spec output\n\n## Your Mission\n\nImplement the spec."


def _make_config(**overrides):
    config = MagicMock()
    config.git_root = overrides.pop("git_root", Path("/repo"))
    config.village_dir = config.git_root / ".village"
    config.traces_dir = config.git_root / ".village" / "traces"
    config.agents = {}
    config.__dict__.update(overrides)
    return config


class TestBuildGoalContext:
    def test_no_goals_file(self):
        config = _make_config()
        with patch("village.contracts.Path") as MockPath:
            MockPath.return_value.__truediv__ = MagicMock(return_value=MagicMock(exists=lambda: False))
            result = _build_goal_context(config, "some task", "some description")
            assert result == ""

    def test_empty_goals(self):
        config = _make_config()
        with patch("village.goals.parse_goals", return_value=[]):
            result = _build_goal_context(config, "some task", "some description")
            assert result == ""

    def test_no_active_goals(self):
        config = _make_config()
        goals = [Goal(id="G1", title="Done", description="completed", status="done")]
        with patch("village.goals.parse_goals", return_value=goals):
            with patch("village.goals.get_active_goals", return_value=[]):
                result = _build_goal_context(config, "task", "desc")
                assert result == ""

    def test_matches_best_goal_by_word_overlap(self):
        config = _make_config()
        goals = [
            Goal(id="G1", title="authentication", description="implement user login", status="active"),
            Goal(id="G2", title="payments", description="process transactions", status="active"),
        ]
        with patch("village.goals.parse_goals", return_value=goals):
            with patch("village.goals.get_active_goals", return_value=goals):
                with patch("village.goals.get_goal_chain", return_value=goals[:1]) as mock_chain:
                    result = _build_goal_context(config, "user login", "fix authentication")
                    assert "G1" in result
                    assert "authentication" in result
                    mock_chain.assert_called_once()

    def test_falls_back_to_first_active_goal(self):
        config = _make_config()
        goals = [
            Goal(id="G1", title="unrelated", description="nothing matching", status="active"),
        ]
        with patch("village.goals.parse_goals", return_value=goals):
            with patch("village.goals.get_active_goals", return_value=goals):
                with patch("village.goals.get_goal_chain", return_value=goals):
                    result = _build_goal_context(config, "xyzzy", "plugh")
                    assert "G1" in result
                    assert "unrelated" in result

    def test_includes_objectives(self):
        config = _make_config()
        goals = [
            Goal(
                id="G1",
                title="auth",
                description="implement auth",
                status="active",
                objectives=[
                    "add login page",
                    "add session handling",
                    "add password reset",
                    "add MFA",
                    "add SSO",
                    "extra objective",
                ],
            ),
        ]
        with patch("village.goals.parse_goals", return_value=goals):
            with patch("village.goals.get_active_goals", return_value=goals):
                with patch("village.goals.get_goal_chain", return_value=goals):
                    result = _build_goal_context(config, "auth login", "implement authentication")
                    assert "Key objectives:" in result
                    assert "- add login page" in result
                    assert "- add MFA" in result
                    assert "extra objective" not in result

    def test_goal_chain_display(self):
        config = _make_config()
        parent = Goal(id="G1", title="Parent", description="parent goal", status="active")
        child = Goal(id="G2", title="Child", description="child goal", status="active", parent="G1")
        chain = [parent, child]

        with patch("village.goals.parse_goals", return_value=[parent, child]):
            with patch("village.goals.get_active_goals", return_value=[child]):
                with patch("village.goals.get_goal_chain", return_value=chain):
                    result = _build_goal_context(config, "child work", "do child stuff")
                    assert "G1: Parent" in result
                    assert "G2: Child" in result
                    assert "→" in result

    def test_exception_returns_empty(self):
        config = _make_config()
        with patch("village.goals.parse_goals", side_effect=Exception("parse error")):
            result = _build_goal_context(config, "task", "desc")
            assert result == ""

    def test_ignores_short_words_in_scoring(self):
        config = _make_config()
        goals = [
            Goal(id="G1", title="auth system", description="implement user authentication system", status="active"),
            Goal(id="G2", title="other thing", description="a an the of", status="active"),
        ]
        with patch("village.goals.parse_goals", return_value=goals):
            with patch("village.goals.get_active_goals", return_value=goals):
                with patch("village.goals.get_goal_chain", return_value=goals[:1]):
                    result = _build_goal_context(config, "auth", "user system")
                    assert "G1" in result


class TestGenerateSpecContract:
    def test_basic_spec_contract(self):
        config = _make_config()
        spec_path = Path("/repo/specs/001-feature.md")
        spec_content = "# Feature Spec\n\nImplement feature X"

        with patch("village.ppc.generate_ppc_contract", return_value=PPC_SPEC_OUTPUT):
            envelope = generate_spec_contract(
                spec_path, spec_content, "build", Path("/worktrees"), "win-1", config=config
            )

        assert envelope.task_id == "001-feature"
        assert envelope.format == "markdown"
        assert envelope.ppc_profile == "spec"
        assert "PPC spec output" in envelope.content

    def test_spec_contract_missing_file_falls_through_to_ppc(self):
        config = _make_config()

        agent_config = MagicMock()
        config.agents = {"build": agent_config}

        spec_path = Path("/repo/specs/001-feature.md")
        spec_content = "# Feature Spec"

        with patch("village.ppc.generate_ppc_contract", return_value=PPC_SPEC_OUTPUT):
            envelope = generate_spec_contract(
                spec_path, spec_content, "build", Path("/worktrees"), "win-1", config=config
            )

        assert "PPC spec output" in envelope.content
