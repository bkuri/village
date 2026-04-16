from dataclasses import dataclass, field

from village.onboard.detector import ProjectInfo


@dataclass
class ScaffoldTemplate:
    language: str
    framework: str | None = None
    build_commands: list[str] = field(default_factory=list)
    test_commands: list[str] = field(default_factory=list)
    lint_commands: list[str] = field(default_factory=list)
    typecheck_commands: list[str] = field(default_factory=list)
    common_deps: list[str] = field(default_factory=list)
    directory_structure: dict[str, str] = field(default_factory=dict)
    conventions: list[str] = field(default_factory=list)
    config_template: str = ""


_PYTHON_CLI = ScaffoldTemplate(
    language="python",
    framework="cli",
    build_commands=["uv sync", "uv pip install -e ."],
    test_commands=["uv run pytest", "uv run pytest tests/test_module.py", "uv run pytest -k test_name"],
    lint_commands=["uv run ruff check .", "uv run ruff check --fix .", "uv run ruff format ."],
    typecheck_commands=["uv run mypy src/"],
    common_deps=["click", "httpx"],
    directory_structure={
        "src/": "Source code",
        "tests/": "Test files",
        "pyproject.toml": "Project configuration",
    },
    conventions=[
        "Use pathlib.Path for file I/O",
        "CLI options in kebab-case",
        "Type hints on all params and returns",
        "Use click.echo() never print()",
    ],
    config_template="",
)

_PYTHON_WEB = ScaffoldTemplate(
    language="python",
    framework="fastapi",
    build_commands=["uv sync", "uvicorn app.main:app --reload"],
    test_commands=["uv run pytest", "uv run pytest tests/ -v"],
    lint_commands=["uv run ruff check .", "uv run ruff format ."],
    typecheck_commands=["uv run mypy app/"],
    common_deps=["fastapi", "uvicorn", "httpx", "pydantic"],
    directory_structure={
        "app/": "Application code",
        "app/api/": "API routes",
        "app/models/": "Data models",
        "tests/": "Test files",
        "pyproject.toml": "Project configuration",
    },
    conventions=[
        "Use dependency injection for DB sessions",
        "Pydantic models for request/response validation",
        "Type hints on all params and returns",
    ],
)

_PYTHON_FLASK = ScaffoldTemplate(
    language="python",
    framework="flask",
    build_commands=["uv sync", "flask run"],
    test_commands=["uv run pytest", "uv run pytest tests/ -v"],
    lint_commands=["uv run ruff check .", "uv run ruff format ."],
    typecheck_commands=["uv run mypy app/"],
    common_deps=["flask", "httpx"],
    directory_structure={
        "app/": "Application code",
        "app/routes/": "Route blueprints",
        "app/models/": "Data models",
        "tests/": "Test files",
        "pyproject.toml": "Project configuration",
    },
    conventions=[
        "Use Blueprints for route organization",
        "Use application factory pattern",
        "Type hints on all params and returns",
    ],
)

_PYTHON_DJANGO = ScaffoldTemplate(
    language="python",
    framework="django",
    build_commands=["uv sync", "python manage.py runserver"],
    test_commands=["uv run pytest", "python manage.py test"],
    lint_commands=["uv run ruff check .", "uv run ruff format ."],
    typecheck_commands=["uv run mypy ."],
    common_deps=["django", "httpx"],
    directory_structure={
        "app/": "Django application",
        "app/models.py": "Data models",
        "app/views.py": "View functions/classes",
        "app/urls.py": "URL routing",
        "tests/": "Test files",
        "manage.py": "Django management script",
        "pyproject.toml": "Project configuration",
    },
    conventions=[
        "Use Django ORM for database operations",
        "Follow Django's MVT pattern",
        "Type hints on all params and returns",
    ],
)

_PYTHON_LIB = ScaffoldTemplate(
    language="python",
    framework=None,
    build_commands=["uv sync", "uv pip install -e ."],
    test_commands=["uv run pytest", "uv run pytest --cov"],
    lint_commands=["uv run ruff check .", "uv run ruff format ."],
    typecheck_commands=["uv run mypy src/"],
    common_deps=[],
    directory_structure={
        "src/": "Source code",
        "tests/": "Test files",
        "pyproject.toml": "Project configuration",
    },
    conventions=[
        "Use pathlib.Path for file I/O",
        "Type hints on all params and returns",
        "Keep public API small and documented",
    ],
)

_TYPESCRIPT_NODE = ScaffoldTemplate(
    language="typescript",
    framework=None,
    build_commands=["npm install", "npm run build"],
    test_commands=["npm test", "npm run test:watch"],
    lint_commands=["npm run lint", "npm run lint:fix"],
    typecheck_commands=["npx tsc --noEmit"],
    common_deps=["typescript", "@types/node"],
    directory_structure={
        "src/": "Source code",
        "tests/": "Test files",
        "tsconfig.json": "TypeScript configuration",
        "package.json": "Project configuration",
    },
    conventions=[
        "Use strict TypeScript",
        "Prefer interfaces over types",
        "No any types",
    ],
)

_RUST_CLI = ScaffoldTemplate(
    language="rust",
    framework=None,
    build_commands=["cargo build", "cargo build --release"],
    test_commands=["cargo test", "cargo test test_name"],
    lint_commands=["cargo clippy", "cargo clippy -- -D warnings"],
    typecheck_commands=["cargo check"],
    common_deps=["clap", "serde"],
    directory_structure={
        "src/": "Source code",
        "tests/": "Integration tests",
        "Cargo.toml": "Project configuration",
    },
    conventions=[
        "Use Result<T, E> for error handling",
        "Follow rustfmt defaults",
        "Document public APIs with doc comments",
    ],
)

_GO_CLI = ScaffoldTemplate(
    language="go",
    framework=None,
    build_commands=["go build ./...", "go install"],
    test_commands=["go test ./...", "go test -v ./..."],
    lint_commands=["golangci-lint run"],
    typecheck_commands=["go vet ./..."],
    common_deps=[],
    directory_structure={
        "cmd/": "Application entrypoints",
        "internal/": "Internal packages",
        "pkg/": "Public packages",
        "go.mod": "Module definition",
    },
    conventions=[
        "Follow standard Go project layout",
        "Use context.Context for all I/O operations",
        "Handle errors explicitly, no panic in libraries",
    ],
)

_GENERIC = ScaffoldTemplate(
    language="unknown",
    framework=None,
    build_commands=["make", "make build"],
    test_commands=["make test"],
    lint_commands=["make lint"],
    typecheck_commands=[],
    common_deps=[],
    directory_structure={},
    conventions=[
        "Document your build/test/lint commands",
        "Type hints where applicable",
        "Keep dependencies minimal",
    ],
)


_SCAFFOLDS: list[ScaffoldTemplate] = [
    _PYTHON_CLI,
    _PYTHON_WEB,
    _PYTHON_FLASK,
    _PYTHON_DJANGO,
    _PYTHON_LIB,
    _TYPESCRIPT_NODE,
    _RUST_CLI,
    _GO_CLI,
    _GENERIC,
]


def get_scaffold(info: ProjectInfo) -> ScaffoldTemplate:
    if info.language == "python":
        if info.framework == "fastapi":
            return _PYTHON_WEB
        if info.framework == "flask":
            return _PYTHON_FLASK
        if info.framework == "django":
            return _PYTHON_DJANGO
        if info.framework == "cli":
            return _PYTHON_CLI
        return _PYTHON_LIB

    if info.language in ("javascript", "typescript"):
        return _TYPESCRIPT_NODE

    if info.language == "rust":
        return _RUST_CLI

    if info.language == "go":
        return _GO_CLI

    return _GENERIC


def all_scaffolds() -> list[ScaffoldTemplate]:
    return list(_SCAFFOLDS)
