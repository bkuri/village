"""Test prompt generation via PPC (hard dependency)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from village.chat.errors import PromptGenerationError
from village.chat.prompts import ChatMode, _compile_ppc_prompt, generate_initial_prompt, generate_mode_prompt
from village.probes.tools import SubprocessError


def _make_config(git_root: Path | None = None) -> MagicMock:
    config = MagicMock()
    config.git_root = git_root or Path("/repo")
    return config


def test_generate_mode_prompt_returns_ppc_backend(tmp_path: Path):
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "village-knowledge-share.yml").write_text("key: value")

    config = _make_config(git_root=tmp_path)

    with patch("village.chat.prompts.run_command_output_cwd", return_value="# PPC prompt"):
        prompt, backend = generate_mode_prompt(config, ChatMode.KNOWLEDGE_SHARE)

        assert prompt == "# PPC prompt"
        assert backend == "ppc"


def test_generate_initial_prompt_delegates_to_mode(tmp_path: Path):
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "village-knowledge-share.yml").write_text("key: value")

    config = _make_config(git_root=tmp_path)

    with patch("village.chat.prompts.run_command_output_cwd", return_value="# Initial"):
        prompt, backend = generate_initial_prompt(config)

        assert prompt == "# Initial"
        assert backend == "ppc"


def test_compile_ppc_prompt_success(tmp_path: Path):
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "village-knowledge-share.yml").write_text("key: value")

    config = _make_config(git_root=tmp_path)

    with patch("village.chat.prompts.run_command_output_cwd", return_value="# Compiled prompt"):
        result = _compile_ppc_prompt(config, ChatMode.KNOWLEDGE_SHARE)

        assert result == "# Compiled prompt"


def test_compile_ppc_prompt_profile_not_found(tmp_path: Path):
    config = _make_config(git_root=tmp_path)

    with pytest.raises(PromptGenerationError, match="PPC profile not found"):
        _compile_ppc_prompt(config, ChatMode.KNOWLEDGE_SHARE)


def test_compile_ppc_prompt_subprocess_error(tmp_path: Path):
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "village-task-create.yml").write_text("key: value")

    config = _make_config(git_root=tmp_path)

    with patch("village.chat.prompts.run_command_output_cwd", side_effect=SubprocessError("fail")):
        with pytest.raises(PromptGenerationError, match="PPC compilation failed"):
            _compile_ppc_prompt(config, ChatMode.TASK_CREATE)
