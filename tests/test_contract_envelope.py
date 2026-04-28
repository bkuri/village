"""Test contract envelope generation."""

import os
from pathlib import Path
from unittest.mock import patch

from village.contracts import ContractEnvelope, generate_contract


def test_generate_contract_ppc(tmp_path: Path):
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True)

    village_dir = tmp_path / ".village"
    village_dir.mkdir(parents=True, exist_ok=True)
    config_file = village_dir / "config"
    config_file.write_text("""[agent.build]
ppc_mode=build
ppc_traits=conservative,terse
ppc_format=markdown
""")

    os.chdir(tmp_path)
    from village.config import get_config

    config = get_config()

    with patch("village.ppc.generate_ppc_contract", return_value="# PPC output\n"):
        envelope = generate_contract("bd-a3f8", "build", tmp_path / ".worktrees/bd-a3f8", "build-1-bd-a3f8", config)

        assert envelope.task_id == "bd-a3f8"
        assert envelope.agent == "build"
        assert "# PPC output" in envelope.content
        assert envelope.ppc_profile == "ppc:build"
        assert len(envelope.warnings) == 0


def test_contract_envelope_to_json():
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
