"""Test spec-aware contract generation."""

import os
from pathlib import Path

from village.config import Config
from village.contracts import generate_spec_contract


def _make_config(git_root: Path) -> Config:
    village_dir = git_root / ".village"
    return Config(
        git_root=git_root,
        village_dir=village_dir,
        worktrees_dir=git_root / ".worktrees",
        tmux_session="test-session",
    )


def test_generate_spec_contract_basic(tmp_path: Path):
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True)

    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()
    spec_path = specs_dir / "001-test-spec.md"
    spec_path.write_text("# Test Spec\n\n## Requirements\n- FR-1: Do something\n  - [ ] Verify it works\n")

    config = _make_config(tmp_path)
    os.chdir(tmp_path)

    envelope = generate_spec_contract(
        spec_path=spec_path,
        spec_content=spec_path.read_text(),
        agent="worker",
        worktree_path=tmp_path / ".worktrees" / "001-test-spec",
        window_name="builder-1-001-test-spec",
        config=config,
    )

    assert envelope.task_id == "001-test-spec"
    assert envelope.agent == "worker"
    assert envelope.format == "markdown"
    assert "001-test-spec.md" in envelope.content
    assert "Do something" in envelope.content
    assert "Verify it works" in envelope.content
    assert "<promise>DONE</promise>" in envelope.content
    assert envelope.ppc_profile == "spec"


def test_generate_spec_contract_with_inspect_notes(tmp_path: Path):
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True)

    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()
    spec_path = specs_dir / "002-advanced.md"
    spec_path.write_text(
        "# Advanced Spec\n\n## Requirements\n- FR-1: Build feature\n"
        "## Inspect Notes\n\n### IN-1: Thread Safety\nMust use locks.\n"
    )

    config = _make_config(tmp_path)
    os.chdir(tmp_path)

    envelope = generate_spec_contract(
        spec_path=spec_path,
        spec_content=spec_path.read_text(),
        agent="worker",
        worktree_path=tmp_path / ".worktrees" / "002-advanced",
        window_name="builder-1-002-advanced",
        config=config,
    )

    assert "Inspect Notes" in envelope.content
    assert "Thread Safety" in envelope.content
    assert "Must use locks" in envelope.content


def test_generate_spec_contract_with_custom_contract(tmp_path: Path):
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True)

    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir()
    custom = contracts_dir / "build.md"
    custom.write_text("# Custom Build Instructions\n\nFollow these rules.")

    village_dir = tmp_path / ".village"
    village_dir.mkdir(parents=True, exist_ok=True)
    config_file = village_dir / "config"
    config_file.write_text("[agent.worker]\ncontract=contracts/build.md\n")

    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()
    spec_path = specs_dir / "003-custom.md"
    spec_path.write_text("# Custom Spec\n\n## Requirements\n- FR-1: Custom feature\n")

    os.chdir(tmp_path)
    config = _make_config(tmp_path)

    from village.config import AgentConfig

    config.agents = {"worker": AgentConfig(contract="contracts/build.md")}

    envelope = generate_spec_contract(
        spec_path=spec_path,
        spec_content=spec_path.read_text(),
        agent="worker",
        worktree_path=tmp_path / ".worktrees" / "003-custom",
        window_name="builder-1-003-custom",
        config=config,
    )

    assert "Custom Build Instructions" in envelope.content
    assert envelope.ppc_profile == "file:contracts/build.md"


def test_generate_spec_contract_to_json(tmp_path: Path):
    import json
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True)

    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()
    spec_path = specs_dir / "004-json.md"
    spec_path.write_text("# JSON Test\n\n## Requirements\n- FR-1: Test\n")

    config = _make_config(tmp_path)
    os.chdir(tmp_path)

    envelope = generate_spec_contract(
        spec_path=spec_path,
        spec_content=spec_path.read_text(),
        agent="worker",
        worktree_path=tmp_path / ".worktrees" / "004-json",
        window_name="builder-1-004-json",
        config=config,
    )

    json_str = envelope.to_json()
    parsed = json.loads(json_str)
    assert parsed["version"] == 1
    assert parsed["format"] == "markdown"
    assert parsed["task_id"] == "004-json"
    assert parsed["agent"] == "worker"
    assert "JSON Test" in parsed["content"]
