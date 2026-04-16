from village.onboard.detector import ProjectInfo
from village.onboard.scaffolds import all_scaffolds, get_scaffold


class TestGetScaffold:
    def test_python_cli_project(self) -> None:
        info = ProjectInfo(language="python", framework="cli")
        scaffold = get_scaffold(info)
        assert scaffold.language == "python"
        assert scaffold.framework == "cli"
        assert "uv run pytest" in scaffold.test_commands
        assert "uv run ruff check ." in scaffold.lint_commands

    def test_python_web_fastapi(self) -> None:
        info = ProjectInfo(language="python", framework="fastapi")
        scaffold = get_scaffold(info)
        assert scaffold.language == "python"
        assert scaffold.framework == "fastapi"
        assert "fastapi" in scaffold.common_deps

    def test_python_web_flask(self) -> None:
        info = ProjectInfo(language="python", framework="flask")
        scaffold = get_scaffold(info)
        assert scaffold.language == "python"
        assert scaffold.framework == "flask"
        assert "flask" in scaffold.common_deps
        assert "Blueprints" in " ".join(scaffold.conventions)

    def test_python_web_django(self) -> None:
        info = ProjectInfo(language="python", framework="django")
        scaffold = get_scaffold(info)
        assert scaffold.language == "python"
        assert scaffold.framework == "django"
        assert "django" in scaffold.common_deps
        assert "Django" in " ".join(scaffold.conventions)

    def test_python_lib_no_framework(self) -> None:
        info = ProjectInfo(language="python", framework=None)
        scaffold = get_scaffold(info)
        assert scaffold.language == "python"
        assert scaffold.framework is None
        assert "uv run pytest --cov" in scaffold.test_commands

    def test_rust_project(self) -> None:
        info = ProjectInfo(language="rust")
        scaffold = get_scaffold(info)
        assert scaffold.language == "rust"
        assert "cargo test" in scaffold.test_commands
        assert "cargo clippy" in scaffold.lint_commands

    def test_go_project(self) -> None:
        info = ProjectInfo(language="go")
        scaffold = get_scaffold(info)
        assert scaffold.language == "go"
        assert "go test ./..." in scaffold.test_commands
        assert "golangci-lint run" in scaffold.lint_commands

    def test_typescript_project(self) -> None:
        info = ProjectInfo(language="typescript")
        scaffold = get_scaffold(info)
        assert scaffold.language == "typescript"
        assert "npm test" in scaffold.test_commands
        assert "npx tsc --noEmit" in scaffold.typecheck_commands

    def test_javascript_project(self) -> None:
        info = ProjectInfo(language="javascript")
        scaffold = get_scaffold(info)
        assert scaffold.language == "typescript"

    def test_unknown_language_returns_generic(self) -> None:
        info = ProjectInfo(language="unknown")
        scaffold = get_scaffold(info)
        assert scaffold.language == "unknown"
        assert "make test" in scaffold.test_commands

    def test_unrecognized_language_returns_generic(self) -> None:
        info = ProjectInfo(language="cobol")
        scaffold = get_scaffold(info)
        assert scaffold.language == "unknown"


class TestAllScaffolds:
    def test_returns_all_scaffolds(self) -> None:
        scaffolds = all_scaffolds()
        assert len(scaffolds) == 9

    def test_scaffolds_have_build_commands(self) -> None:
        for scaffold in all_scaffolds():
            assert len(scaffold.build_commands) > 0, f"{scaffold.language}/{scaffold.framework} has no build_commands"

    def test_scaffolds_have_test_commands(self) -> None:
        for scaffold in all_scaffolds():
            assert len(scaffold.test_commands) > 0, f"{scaffold.language}/{scaffold.framework} has no test_commands"

    def test_scaffolds_have_language(self) -> None:
        for scaffold in all_scaffolds():
            assert scaffold.language, "scaffold has empty language"

    def test_scaffolds_have_conventions(self) -> None:
        for scaffold in all_scaffolds():
            assert len(scaffold.conventions) > 0, f"{scaffold.language}/{scaffold.framework} has no conventions"
