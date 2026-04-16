"""Test project type detector."""

import json
from pathlib import Path

from village.onboard.detector import ProjectInfo, detect_project


class TestDetectPythonProject:
    """Test Python project detection via pyproject.toml."""

    def test_pyproject_with_pytest_and_ruff(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[project]\nname = 'myapp'\n\n[tool.pytest]\n[tool.ruff]\n",
            encoding="utf-8",
        )
        (tmp_path / "uv.lock").touch()

        info = detect_project(tmp_path)

        assert info.language == "python"
        assert info.build_tool == "uv"
        assert info.test_runner == "pytest"
        assert info.linter == "ruff"
        assert info.package_file == pyproject
        assert "pyproject.toml" in info.detected_files

    def test_pyproject_with_fastapi_framework(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            "[project]\nname = 'api'\ndependencies = ['fastapi']\n",
            encoding="utf-8",
        )

        info = detect_project(tmp_path)

        assert info.language == "python"
        assert info.framework == "fastapi"

    def test_pyproject_with_click_framework(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            "[project]\nname = 'cli-app'\ndependencies = ['click']\n",
            encoding="utf-8",
        )

        info = detect_project(tmp_path)

        assert info.language == "python"
        assert info.framework == "cli"

    def test_setup_py_fallback(self, tmp_path: Path) -> None:
        (tmp_path / "setup.py").write_text("from setuptools import setup\nsetup()\n", encoding="utf-8")

        info = detect_project(tmp_path)

        assert info.language == "python"
        assert info.build_tool == "setuptools"
        assert "setup.py" in info.detected_files

    def test_requirements_txt_only(self, tmp_path: Path) -> None:
        (tmp_path / "requirements.txt").write_text("flask==2.0\n", encoding="utf-8")

        info = detect_project(tmp_path)

        assert info.language == "python"
        assert info.build_tool == "pip"
        assert "requirements.txt" in info.detected_files

    def test_src_dir_entry_point(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'pkg'\n", encoding="utf-8")
        pkg_dir = tmp_path / "src" / "mypkg"
        pkg_dir.mkdir(parents=True)

        info = detect_project(tmp_path)

        assert info.entry_point == "src/mypkg"

    def test_matching_dir_entry_point(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'myproj'\n", encoding="utf-8")
        (tmp_path / tmp_path.name).mkdir()

        info = detect_project(tmp_path)

        assert info.entry_point == tmp_path.name

    def test_poetry_build_tool(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            "[tool.poetry]\nname = 'poetry-app'\n",
            encoding="utf-8",
        )

        info = detect_project(tmp_path)

        assert info.build_tool == "poetry"

    def test_hatch_build_tool(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            "[tool.hatch.build]\ntargets = ['wheels']\n",
            encoding="utf-8",
        )

        info = detect_project(tmp_path)

        assert info.build_tool == "hatch"

    def test_default_setuptools_build_tool(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'basic'\n", encoding="utf-8")

        info = detect_project(tmp_path)

        assert info.build_tool == "setuptools"

    def test_flake8_linter_fallback(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            "[project]\nname = 'app'\n[tool.flake8]\n",
            encoding="utf-8",
        )

        info = detect_project(tmp_path)

        assert info.linter == "flake8"


class TestDetectJavaScriptProject:
    """Test JavaScript/TypeScript project detection via package.json."""

    def test_react_project(self, tmp_path: Path) -> None:
        pkg = {"dependencies": {"react": "^18.0.0"}, "devDependencies": {}}
        (tmp_path / "package.json").write_text(json.dumps(pkg), encoding="utf-8")

        info = detect_project(tmp_path)

        assert info.language == "javascript"
        assert info.framework == "react"
        assert info.build_tool == "npm"

    def test_react_with_typescript(self, tmp_path: Path) -> None:
        pkg = {
            "dependencies": {"react": "^18.0.0"},
            "devDependencies": {"typescript": "^5.0.0"},
        }
        (tmp_path / "package.json").write_text(json.dumps(pkg), encoding="utf-8")

        info = detect_project(tmp_path)

        assert info.language == "typescript"
        assert info.framework == "react"

    def test_nextjs_project(self, tmp_path: Path) -> None:
        pkg = {"dependencies": {"next": "^14.0.0"}, "devDependencies": {}}
        (tmp_path / "package.json").write_text(json.dumps(pkg), encoding="utf-8")

        info = detect_project(tmp_path)

        assert info.framework == "nextjs"

    def test_nextjs_with_react_detected_as_nextjs(self, tmp_path: Path) -> None:
        pkg = {
            "dependencies": {"next": "^14.0.0", "react": "^18.0.0", "react-dom": "^18.0.0"},
            "devDependencies": {"typescript": "^5.0.0"},
        }
        (tmp_path / "package.json").write_text(json.dumps(pkg), encoding="utf-8")

        info = detect_project(tmp_path)

        assert info.framework == "nextjs"
        assert info.language == "typescript"

    def test_vue_project(self, tmp_path: Path) -> None:
        pkg = {"dependencies": {"vue": "^3.0.0"}, "devDependencies": {}}
        (tmp_path / "package.json").write_text(json.dumps(pkg), encoding="utf-8")

        info = detect_project(tmp_path)

        assert info.framework == "vue"

    def test_express_project(self, tmp_path: Path) -> None:
        pkg = {"dependencies": {"express": "^4.0.0"}, "devDependencies": {}}
        (tmp_path / "package.json").write_text(json.dumps(pkg), encoding="utf-8")

        info = detect_project(tmp_path)

        assert info.framework == "express"

    def test_yarn_build_tool(self, tmp_path: Path) -> None:
        pkg = {"dependencies": {}, "devDependencies": {}}
        (tmp_path / "package.json").write_text(json.dumps(pkg), encoding="utf-8")
        (tmp_path / "yarn.lock").touch()

        info = detect_project(tmp_path)

        assert info.build_tool == "yarn"

    def test_pnpm_build_tool(self, tmp_path: Path) -> None:
        pkg = {"dependencies": {}, "devDependencies": {}}
        (tmp_path / "package.json").write_text(json.dumps(pkg), encoding="utf-8")
        (tmp_path / "pnpm-lock.yaml").touch()

        info = detect_project(tmp_path)

        assert info.build_tool == "pnpm"

    def test_bun_build_tool(self, tmp_path: Path) -> None:
        pkg = {"dependencies": {}, "devDependencies": {}}
        (tmp_path / "package.json").write_text(json.dumps(pkg), encoding="utf-8")
        (tmp_path / "bun.lockb").touch()

        info = detect_project(tmp_path)

        assert info.build_tool == "bun"

    def test_jest_test_runner(self, tmp_path: Path) -> None:
        pkg = {"dependencies": {}, "devDependencies": {"jest": "^29.0.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg), encoding="utf-8")

        info = detect_project(tmp_path)

        assert info.test_runner == "jest"

    def test_vitest_test_runner(self, tmp_path: Path) -> None:
        pkg = {"dependencies": {}, "devDependencies": {"vitest": "^1.0.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg), encoding="utf-8")

        info = detect_project(tmp_path)

        assert info.test_runner == "vitest"

    def test_eslint_linter(self, tmp_path: Path) -> None:
        pkg = {"dependencies": {}, "devDependencies": {"eslint": "^8.0.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg), encoding="utf-8")

        info = detect_project(tmp_path)

        assert info.linter == "eslint"

    def test_malformed_package_json(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("not valid json{{{", encoding="utf-8")

        info = detect_project(tmp_path)

        assert info.language == "javascript"
        assert info.build_tool == "npm"


class TestDetectRustProject:
    """Test Rust project detection via Cargo.toml."""

    def test_cargo_project(self, tmp_path: Path) -> None:
        (tmp_path / "Cargo.toml").write_text("[package]\nname = 'myapp'\n", encoding="utf-8")
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.rs").write_text("fn main() {}\n", encoding="utf-8")

        info = detect_project(tmp_path)

        assert info.language == "rust"
        assert info.build_tool == "cargo"
        assert info.test_runner == "cargo test"
        assert info.linter == "clippy"
        assert info.entry_point == "src/main.rs"
        assert "Cargo.toml" in info.detected_files

    def test_rust_library(self, tmp_path: Path) -> None:
        (tmp_path / "Cargo.toml").write_text("[package]\nname = 'mylib'\n", encoding="utf-8")
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "lib.rs").write_text("pub fn hello() {}\n", encoding="utf-8")

        info = detect_project(tmp_path)

        assert info.framework == "library"


class TestDetectGoProject:
    """Test Go project detection via go.mod."""

    def test_go_project(self, tmp_path: Path) -> None:
        (tmp_path / "go.mod").write_text("module github.com/user/myapp\n", encoding="utf-8")

        info = detect_project(tmp_path)

        assert info.language == "go"
        assert info.build_tool == "go"
        assert info.test_runner == "go test"
        assert info.linter == "golangci-lint"
        assert "go.mod" in info.detected_files

    def test_go_with_cmd_dir(self, tmp_path: Path) -> None:
        (tmp_path / "go.mod").write_text("module github.com/user/cli\n", encoding="utf-8")
        (tmp_path / "cmd").mkdir()

        info = detect_project(tmp_path)

        assert info.entry_point == "cmd/"


class TestDetectUnknownProject:
    """Test detection when no known package files exist."""

    def test_no_package_file(self, tmp_path: Path) -> None:
        info = detect_project(tmp_path)

        assert info.language == "unknown"
        assert info.build_tool is None
        assert info.package_file is None
        assert info.needs_onboarding is True


class TestNeedsOnboarding:
    """Test AGENTS.md template detection for onboarding need."""

    def test_template_agents_md_needs_onboarding(self, tmp_path: Path) -> None:
        (tmp_path / "AGENTS.md").write_text(
            "# AGENTS.md\n\n## Overview\n<fill in>\n",
            encoding="utf-8",
        )

        info = detect_project(tmp_path)

        assert info.needs_onboarding is True
        assert info.has_existing_agents_md is True

    def test_missing_agents_md_needs_onboarding(self, tmp_path: Path) -> None:
        info = detect_project(tmp_path)

        assert info.needs_onboarding is True
        assert info.has_existing_agents_md is False

    def test_complete_agents_md_no_onboarding(self, tmp_path: Path) -> None:
        (tmp_path / "AGENTS.md").write_text(
            "# AGENTS.md\n\n## Build\nRun `make build`.\n\n## Test\nRun `make test`.\n",
            encoding="utf-8",
        )

        info = detect_project(tmp_path)

        assert info.needs_onboarding is False
        assert info.has_existing_agents_md is True

    def test_template_marker_describe_key_conventions(self, tmp_path: Path) -> None:
        (tmp_path / "AGENTS.md").write_text(
            "# AGENTS.md\nDescribe key conventions here.\n",
            encoding="utf-8",
        )

        info = detect_project(tmp_path)

        assert info.needs_onboarding is True

    def test_template_marker_brief_description(self, tmp_path: Path) -> None:
        (tmp_path / "AGENTS.md").write_text(
            "# AGENTS.md\nBrief description of the project.\n",
            encoding="utf-8",
        )

        info = detect_project(tmp_path)

        assert info.needs_onboarding is True


class TestDetectProjectMetadata:
    """Test common metadata detection across project types."""

    def test_project_name_set(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")

        info = detect_project(tmp_path)

        assert info.project_name == tmp_path.name

    def test_readme_detection(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("# My Project\n", encoding="utf-8")

        info = detect_project(tmp_path)

        assert info.has_existing_readme is True

    def test_no_readme(self, tmp_path: Path) -> None:
        info = detect_project(tmp_path)

        assert info.has_existing_readme is False

    def test_relative_path_resolved(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")
        relative = Path(tmp_path.name)

        info = detect_project(relative)

        assert info.project_name == tmp_path.name

    def test_default_project_info_values(self) -> None:
        info = ProjectInfo()

        assert info.language == "unknown"
        assert info.framework is None
        assert info.build_tool is None
        assert info.test_runner is None
        assert info.linter is None
        assert info.package_file is None
        assert info.entry_point is None
        assert info.has_existing_agents_md is False
        assert info.has_existing_readme is False
        assert info.needs_onboarding is True
        assert info.project_name == ""
        assert info.detected_files == []
