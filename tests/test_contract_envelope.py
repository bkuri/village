"""Test contract envelope generation."""

import os
from datetime import datetime
from pathlib import Path

from village.config import get_config
from village.contracts import ContractEnvelope, generate_contract, generate_fallback_contract


def test_generate_contract_custom_file(tmp_path: Path):
    """Test contract generation with custom file."""
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True)

    # Create custom contract file
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir()
    custom_contract = contracts_dir / "build.md"
    custom_contract.write_text("# Custom build contract")

    # Create config
    village_dir = tmp_path / ".village"
    village_dir.mkdir(parents=True, exist_ok=True)
    config_file = village_dir / "config"
    config_file.write_text("""[agent.build]
contract=contracts/build.md
""")

    os.chdir(tmp_path)
    config = get_config()

    envelope = generate_contract(
        "bd-a3f8", "build", tmp_path / ".worktrees/bd-a3f8", "build-1-bd-a3f8", config
    )

    assert envelope.task_id == "bd-a3f8"
    assert envelope.agent == "build"
    assert envelope.format == "markdown"
    assert "Custom build contract" in envelope.content
    assert envelope.ppc_profile == "file:contracts/build.md"
    assert len(envelope.warnings) == 0


def test_generate_contract_custom_file_not_found(tmp_path: Path):
    """Test contract generation when custom file missing."""
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True)

    # Create config with non-existent contract
    village_dir = tmp_path / ".village"
    village_dir.mkdir(parents=True, exist_ok=True)
    config_file = village_dir / "config"
    config_file.write_text("""[agent.build]
contract=contracts/missing.md
""")

    os.chdir(tmp_path)
    config = get_config()

    envelope = generate_contract(
        "bd-a3f8", "build", tmp_path / ".worktrees/bd-a3f8", "build-1-bd-a3f8", config
    )

    assert envelope.task_id == "bd-a3f8"
    assert envelope.agent == "build"
    assert envelope.format == "markdown"
    # Should use fallback
    assert "## Goal" in envelope.content
    assert "Work on task `bd-a3f8`" in envelope.content
    assert envelope.ppc_profile == "fallback"
    # Check that warning is about contract file
    assert any("contract_file_not_found" in w for w in envelope.warnings)


def test_generate_contract_ppc_available(tmp_path: Path):
    """Test contract generation with PPC."""
    import subprocess
    from unittest.mock import patch

    subprocess.run(["git", "init"], cwd=tmp_path, check=True)

    # Create config
    village_dir = tmp_path / ".village"
    village_dir.mkdir(parents=True, exist_ok=True)
    config_file = village_dir / "config"
    config_file.write_text("""[agent.build]
ppc_mode=build
ppc_traits=conservative,terse
ppc_format=markdown
""")

    os.chdir(tmp_path)
    config = get_config()

    # Mock PPC to be available
    with patch("village.ppc.generate_ppc_contract", return_value=("# PPC output\n", None)):
        with patch(
            "village.probes.ppc.detect_ppc",
            return_value=type(
                "Status", (), {"available": True, "version": "v0.2.0", "prompts_dir": None}
            ),
        ):
            envelope = generate_contract(
                "bd-a3f8", "build", tmp_path / ".worktrees/bd-a3f8", "build-1-bd-a3f8", config
            )

            assert envelope.task_id == "bd-a3f8"
            assert envelope.agent == "build"
            assert "# PPC output" in envelope.content
            assert envelope.ppc_profile == "ppc:build"
            assert envelope.ppc_version == "v0.2.0"
            assert len(envelope.warnings) == 0


def test_generate_contract_ppc_not_available():
    """Test contract generation when PPC not available."""
    from unittest.mock import patch

    config = get_config()

    # Mock PPC to not be available
    with patch("village.ppc.generate_ppc_contract", return_value=(None, "ppc_not_available")):
        with patch(
            "village.probes.ppc.detect_ppc",
            return_value=type(
                "Status", (), {"available": False, "version": None, "prompts_dir": None}
            ),
        ):
            envelope = generate_contract(
                "bd-a3f8", "build", Path("/worktrees/bd-a3f8"), "build-1-bd-a3f8", config
            )

            assert envelope.task_id == "bd-a3f8"
            assert envelope.agent == "build"
            assert "## Goal" in envelope.content  # Fallback template used
            assert envelope.ppc_profile == "fallback"
            assert "ppc_not_available" in envelope.warnings


def test_generate_contract_ppc_fails(tmp_path: Path):
    """Test contract generation when PPC fails."""
    import subprocess
    from unittest.mock import patch

    subprocess.run(["git", "init"], cwd=tmp_path, check=True)

    # Create config
    village_dir = tmp_path / ".village"
    village_dir.mkdir(parents=True, exist_ok=True)
    config_file = village_dir / "config"
    config_file.write_text("""[agent.build]
ppc_mode=build
""")

    os.chdir(tmp_path)
    config = get_config()

    # Mock PPC to fail
    with patch(
        "village.ppc.generate_ppc_contract", return_value=(None, "ppc_execution_failed: error")
    ):
        with patch(
            "village.probes.ppc.detect_ppc",
            return_value=type(
                "Status", (), {"available": True, "version": "v0.2.0", "prompts_dir": None}
            ),
        ):
            envelope = generate_contract(
                "bd-a3f8", "build", Path("/worktrees/bd-a3f8"), "build-1-bd-a3f8", config
            )

            assert envelope.task_id == "bd-a3f8"
            assert envelope.agent == "build"
            assert "## Goal" in envelope.content  # Fallback template used
            assert envelope.ppc_profile == "fallback"
            assert "ppc_execution_failed" in envelope.warnings[0]


def test_contract_envelope_to_json():
    """Test ContractEnvelope serialization."""
    envelope = ContractEnvelope(
        version=1,
        format="markdown",
        task_id="bd-a3f8",
        agent="build",
        content="# Test content",
        warnings=["test_warning"],
        ppc_profile="ppc:build",
        ppc_version="v0.2.0",
        created_at="2026-01-23T12:00:00",
    )

    json_str = envelope.to_json()

    assert '"version": 1' in json_str
    assert '"format": "markdown"' in json_str
    assert '"task_id": "bd-a3f8"' in json_str
    assert '"agent": "build"' in json_str
    assert '"content": "# Test content"' in json_str
    assert '"warnings": ["test_warning"]' in json_str
    assert '"ppc_profile": "ppc:build"' in json_str
    assert '"ppc_version": "v0.2.0"' in json_str
    assert '"created_at": "2026-01-23T12:00:00"' in json_str


def test_generate_fallback_contract():
    """Test fallback contract template."""

    contract = generate_fallback_contract(
        task_id="bd-a3f8",
        agent="build",
        worktree_path=Path("/worktrees/bd-a3f8"),
        git_root=Path("/repo"),
        window_name="build-1-bd-a3f8",
        created_at=datetime(2026, 1, 23, 12, 0, 0),
    )

    assert "# Task: bd-a3f8 (build)" in contract
    assert "## Goal" in contract
    assert "## Constraints" in contract
    assert "## Inputs" in contract
    assert "/worktrees/bd-a3f8" in contract
    assert "/repo" in contract
    assert "build-1-bd-a3f8" in contract
    assert "2026-01-23T12:00:00" in contract
