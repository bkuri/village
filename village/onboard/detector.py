import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ProjectInfo:
    language: str = "unknown"
    framework: str | None = None
    build_tool: str | None = None
    test_runner: str | None = None
    linter: str | None = None
    package_file: Path | None = None
    entry_point: str | None = None
    has_existing_agents_md: bool = False
    has_existing_readme: bool = False
    needs_onboarding: bool = True
    project_name: str = ""
    detected_files: list[str] = field(default_factory=list)


def _check_template_agents_md(path: Path) -> bool:
    agents_md = path / "AGENTS.md"
    if not agents_md.exists():
        return True
    content = agents_md.read_text(encoding="utf-8")
    template_markers = ["<fill in>", "Describe key conventions", "Brief description"]
    return any(marker in content for marker in template_markers)


def _detect_python(path: Path) -> ProjectInfo:
    info = ProjectInfo(language="python", project_name=path.name)

    pyproject = path / "pyproject.toml"
    setup_py = path / "setup.py"
    setup_cfg = path / "setup.cfg"
    requirements = path / "requirements.txt"

    if pyproject.exists():
        info.package_file = pyproject
        info.detected_files.append("pyproject.toml")
        content = pyproject.read_text(encoding="utf-8").lower()

        if "[tool.poetry]" in content:
            info.build_tool = "poetry"
        elif "hatch" in content:
            info.build_tool = "hatch"
        else:
            info.build_tool = "setuptools"

        if "uv" in content or (path / "uv.lock").exists():
            info.build_tool = "uv"

        if "pytest" in content:
            info.test_runner = "pytest"
        if "ruff" in content:
            info.linter = "ruff"
        elif "flake8" in content:
            info.linter = "flake8"
        if "fastapi" in content:
            info.framework = "fastapi"
        elif "flask" in content:
            info.framework = "flask"
        elif "django" in content:
            info.framework = "django"
        elif "click" in content or "typer" in content:
            info.framework = "cli"
    elif setup_py.exists() or setup_cfg.exists():
        info.build_tool = "setuptools"
        info.package_file = setup_py if setup_py.exists() else setup_cfg
        info.detected_files.append(info.package_file.name)
    elif requirements.exists():
        info.build_tool = "pip"
        info.detected_files.append("requirements.txt")

    src_dir = path / "src"
    if src_dir.exists():
        namespace = list(src_dir.iterdir())
        if namespace:
            info.entry_point = f"src/{namespace[0].name}"
    elif (path / path.name).is_dir():
        info.entry_point = path.name

    return info


def _detect_javascript(path: Path) -> ProjectInfo:
    info = ProjectInfo(language="javascript", project_name=path.name)

    package_json = path / "package.json"
    if not package_json.exists():
        info.language = "unknown"
        return info

    info.package_file = package_json
    info.detected_files.append("package.json")

    try:
        data = json.loads(package_json.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        data = {}

    if (path / "yarn.lock").exists():
        info.build_tool = "yarn"
    elif (path / "pnpm-lock.yaml").exists():
        info.build_tool = "pnpm"
    elif (path / "bun.lockb").exists():
        info.build_tool = "bun"
    else:
        info.build_tool = "npm"

    deps = {k.lower() for k in list(data.get("dependencies", {}).keys()) + list(data.get("devDependencies", {}).keys())}

    if "next" in deps:
        info.language = "typescript" if "typescript" in deps else "javascript"
        info.framework = "nextjs"
    elif "react" in deps:
        info.language = "typescript" if "typescript" in deps else "javascript"
        info.framework = "react"
    elif "vue" in deps:
        info.framework = "vue"
    elif "express" in deps:
        info.framework = "express"

    if "jest" in deps:
        info.test_runner = "jest"
    elif "vitest" in deps:
        info.test_runner = "vitest"
    if "eslint" in deps:
        info.linter = "eslint"
    if "typescript" in deps:
        info.language = "typescript"

    return info


def _detect_rust(path: Path) -> ProjectInfo:
    info = ProjectInfo(language="rust", build_tool="cargo", project_name=path.name)

    cargo_toml = path / "Cargo.toml"
    if cargo_toml.exists():
        info.package_file = cargo_toml
        info.detected_files.append("Cargo.toml")
        info.test_runner = "cargo test"
        info.linter = "clippy"

    if (path / "src" / "main.rs").exists():
        info.entry_point = "src/main.rs"

    if (path / "src" / "lib.rs").exists():
        info.framework = "library"

    return info


def _detect_go(path: Path) -> ProjectInfo:
    info = ProjectInfo(language="go", build_tool="go", project_name=path.name)

    go_mod = path / "go.mod"
    if go_mod.exists():
        info.package_file = go_mod
        info.detected_files.append("go.mod")
        info.test_runner = "go test"
        info.linter = "golangci-lint"

    cmd_dir = path / "cmd"
    if cmd_dir.exists():
        info.entry_point = "cmd/"

    return info


_DETECTORS = {
    "python": _detect_python,
    "javascript": _detect_javascript,
    "rust": _detect_rust,
    "go": _detect_go,
}


def _identify_language(path: Path) -> str:
    signals: list[tuple[str, list[str]]] = [
        ("python", ["pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "Pipfile"]),
        ("javascript", ["package.json"]),
        ("rust", ["Cargo.toml"]),
        ("go", ["go.mod"]),
        ("ruby", ["Gemfile"]),
        ("java", ["pom.xml", "build.gradle", "build.gradle.kts"]),
    ]
    for language, filenames in signals:
        for filename in filenames:
            if (path / filename).exists():
                return language
    return "unknown"


def detect_project(path: Path) -> ProjectInfo:
    if not path.is_absolute():
        path = path.resolve()

    language = _identify_language(path)

    detector = _DETECTORS.get(language)
    if detector:
        info = detector(path)
    else:
        info = ProjectInfo(language=language, project_name=path.name)

    info.has_existing_agents_md = (path / "AGENTS.md").exists()
    info.has_existing_readme = (path / "README.md").exists()
    info.needs_onboarding = _check_template_agents_md(path)
    info.project_name = path.name

    return info
