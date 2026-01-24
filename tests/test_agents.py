"""Test agent mapping resolution."""

import os
from pathlib import Path

from village.agents import resolve_agent_args
from village.config import get_config


def test_resolve_agent_args_from_config(tmp_path: Path):
    """Test agent resolution from config file."""
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True)

    village_dir = tmp_path / ".village"
    village_dir.mkdir(parents=True, exist_ok=True)
    config_file = village_dir / "config"
    config_file.write_text("""[DEFAULT]
DEFAULT_AGENT=build

[agent.build]
opencode_args=--mode patch --safe
contract=contracts/build.md
ppc_mode=build
ppc_traits=conservative,terse
ppc_format=markdown

[agent.test]
opencode_args=--mode patch
ppc_mode=ship
""")

    from village.config import get_config

    os.chdir(tmp_path)
    config = get_config()

    # Test build agent
    build_args = resolve_agent_args("build", config)
    assert build_args.agent == "build"
    assert build_args.opencode_args == ["--mode", "patch", "--safe"]

    # Test test agent
    test_args = resolve_agent_args("test", config)
    assert test_args.agent == "test"
    assert test_args.opencode_args == ["--mode", "patch"]


def test_resolve_agent_args_fallback():
    """Test agent resolution fallback (no config)."""
    config = get_config()

    args = resolve_agent_args("unknown_agent", config)
    assert args.agent == "unknown_agent"
    assert args.opencode_args == []


def test_resolve_agent_args_invalid_shell_syntax(tmp_path: Path):
    """Test agent resolution with invalid shell syntax."""
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True)

    village_dir = tmp_path / ".village"
    village_dir.mkdir(parents=True, exist_ok=True)
    config_file = village_dir / "config"
    config_file.write_text("""[agent.build]
opencode_args=--mode "unclosed quote
""")

    os.chdir(tmp_path)
    from village.config import get_config

    config = get_config()

    args = resolve_agent_args("build", config)
    assert args.agent == "build"
    # Should fall back to empty list when shlex.split() fails
    assert args.opencode_args == []


def test_resolve_agent_args_empty_args(tmp_path: Path):
    """Test agent resolution with empty opencode_args."""
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True)

    village_dir = tmp_path / ".village"
    village_dir.mkdir(parents=True, exist_ok=True)
    config_file = village_dir / "config"
    config_file.write_text("""[agent.build]
opencode_args=
""")

    os.chdir(tmp_path)
    from village.config import get_config

    config = get_config()

    args = resolve_agent_args("build", config)
    assert args.agent == "build"
    assert args.opencode_args == []


def test_resolve_agent_args_multiple(tmp_path: Path):
    """Test resolving multiple agents from config."""
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True)

    village_dir = tmp_path / ".village"
    village_dir.mkdir(parents=True, exist_ok=True)
    config_file = village_dir / "config"
    config_file.write_text("""[DEFAULT]
DEFAULT_AGENT=build

[agent.build]
opencode_args=--mode patch --safe

[agent.test]
opencode_args=--mode patch

[agent.deploy]
opencode_args=--deploy
""")

    os.chdir(tmp_path)
    from village.config import get_config

    config = get_config()

    build_args = resolve_agent_args("build", config)
    test_args = resolve_agent_args("test", config)
    deploy_args = resolve_agent_args("deploy", config)

    assert build_args.agent == "build"
    assert build_args.opencode_args == ["--mode", "patch", "--safe"]
    assert test_args.opencode_args == ["--mode", "patch"]
    assert deploy_args.opencode_args == ["--deploy"]


def test_resolve_agent_args_equals_syntax(tmp_path: Path):
    """Test that --mode=patch is preserved as one token."""
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True)

    village_dir = tmp_path / ".village"
    village_dir.mkdir(parents=True, exist_ok=True)
    config_file = village_dir / "config"
    config_file.write_text("""[agent.build]
opencode_args=--mode=patch --safe
""")

    os.chdir(tmp_path)
    from village.config import get_config

    config = get_config()

    args = resolve_agent_args("build", config)
    assert args.agent == "build"
    # --mode=patch should be one token, --safe should be another
    assert args.opencode_args == ["--mode=patch", "--safe"]
