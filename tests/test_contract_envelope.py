"""Test contract envelope generation."""

import os
from pathlib import Path
from unittest.mock import patch

from village.config import get_config
from village.contracts import ContractEnvelope, generate_contract


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

    envelope = generate_contract("bd-a3f8", "build", tmp_path / ".worktrees/bd-a3f8", "build-1-bd-a3f8", config)

    assert envelope.task_id == "bd-a3f8"
    assert envelope.agent == "build"
    assert envelope.format == "markdown"
    assert "Custom build contract" in envelope.content
    assert envelope.ppc_profile == "file:contracts/build.md"
    assert len(envelope.warnings) == 0


def test_generate_contract_custom_file_not_found(tmp_path: Path):
    """Test contract generation when custom file missing (falls through to PPC)."""
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

    # Mock PPC to return content
    with patch("village.ppc.generate_ppc_contract", return_value="# PPC fallback content"):
        envelope = generate_contract("bd-a3f8", "build", tmp_path / ".worktrees/bd-a3f8", "build-1-bd-a3f8", config)

        assert envelope.task_id == "bd-a3f8"
        assert envelope.agent == "build"
        assert envelope.format == "markdown"
        assert "# PPC fallback content" in envelope.content


def test_generate_contract_ppc_available(tmp_path: Path):
    """Test contract generation with PPC."""
    import subprocess

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
    with patch("village.ppc.generate_ppc_contract", return_value="# PPC output\n"):
        envelope = generate_contract("bd-a3f8", "build", tmp_path / ".worktrees/bd-a3f8", "build-1-bd-a3f8", config)

        assert envelope.task_id == "bd-a3f8"
        assert envelope.agent == "build"
        assert "# PPC output" in envelope.content
        assert envelope.ppc_profile == "ppc:build"
        assert len(envelope.warnings) == 0


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
