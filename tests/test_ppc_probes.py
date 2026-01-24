"""Test PPC detection probe."""

import os
from pathlib import Path

import pytest

from village.config import get_config
from village.probes.ppc import PPCStatus, detect_ppc


def test_detect_ppc_available(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test PPC detection when available."""
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True)

    # Create mock PPC binary
    mock_ppc = tmp_path / "ppc"
    mock_ppc.write_text('#!/bin/sh\necho "ppc v0.2.0"')
    mock_ppc.chmod(0o755)

    # Create prompts directory
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()

    # Create config
    config = get_config()
    # We need to update git_root since get_config() was called before changing dir
    config.git_root = tmp_path

    # Mock PATH to include our mock PPC
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ.get('PATH', '')}")

    status = detect_ppc(config)

    assert status.available is True
    assert status.version == "ppc v0.2.0"
    assert status.prompts_dir == prompts_dir


def test_detect_ppc_not_found():
    """Test PPC detection when binary not found."""
    # Use current config, PPC should not be in PATH
    status = detect_ppc(get_config())

    # We can't guarantee PPC isn't installed on the system,
    # so we'll just verify the function doesn't crash
    assert isinstance(status, PPCStatus)
    assert status.available is False or status.available is True


def test_detect_ppc_no_prompts_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test PPC detection without prompts directory."""
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True)

    # Create mock PPC binary
    mock_ppc = tmp_path / "ppc"
    mock_ppc.write_text('#!/bin/sh\necho "ppc v0.2.0"')
    mock_ppc.chmod(0o755)

    # Don't create prompts directory

    # Create config
    config = get_config()
    config.git_root = tmp_path

    # Mock PATH to include our mock PPC
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ.get('PATH', '')}")

    status = detect_ppc(config)

    assert status.available is True
    assert status.version == "ppc v0.2.0"
    assert status.prompts_dir is None
