# Village - Agent Development Guide

## Build, Lint, and Test Commands

### Package Management (uv)
```bash
uv sync                    # Install dependencies
uv add <package>           # Add dependency
uv add --dev <package>     # Add dev dependency
```

### Running the CLI
```bash
uv run village <command>   # Run during development
uv pip install -e . && village <command>  # Install and run
```

### Linting
```bash
uv run ruff check .        # Lint
uv run ruff check --fix .  # Auto-fix
uv run ruff format .       # Format
```

### Type Checking
```bash
uv run mypy village/      # Type check entire module
```

### Testing
```bash
uv run pytest                              # All tests
uv run pytest tests/test_module.py         # Single file
uv run pytest tests/test_module.py::test   # Single test
uv run pytest -k "test_lock_"              # Pattern match
uv run pytest -s                           # Verbose output
uv run pytest --cov=village                # With coverage
```

## Code Style Guidelines

### General Principles
- **Explicit over implicit** - no magic, side effects, or hidden state
- **Truth over intention** - use authoritative handles (tmux pane IDs, file paths)
- **One source of truth** - probe actual state, don't cache
- **Safe by default** - plan/dry-run before mutations
- **Everything inspectable** - plain text, JSON contracts, shell access

### Imports and Formatting
- Group: stdlib → third-party → local imports
- Use `ruff` for all formatting
- Avoid wildcard imports
- Sort with `isort`-compatible ordering (ruff handles this)

### Type Hints
- Use modern syntax (`|` for unions, not `Union`)
- Type all params and returns
- Use `dataclasses` for structured data
- Avoid `Any` - prefer `Unknown` or specific types

### Naming Conventions
- **Files**: `snake_case.py` - `lock_manager.py`, `tmux_probe.py`
- **Classes**: `PascalCase` - `LockManager`, `TmuxProbe`
- **Functions/Variables**: `snake_case` - `get_pane_id()`, `is_active`
- **Constants**: `UPPER_SNAKE_CASE` - `VILLAGE_DIR`, `LOCK_FILE_PATTERN`
- **Private**: `_leading_underscore` - `_parse_pane_id()`
- **CLI options**: `kebab-case` - `--dry-run`, `--detached`

### Error Handling
- Define specific exception types
- Include context in messages (IDs, paths, pane IDs)
- Never catch `Exception` broadly
- Use `click.ClickException` for CLI errors
- Use `sys.exit(code)` for fatal errors

### CLI Structure (Click)
- Use `click` decorators
- Default to plan/dry-run for ambiguous commands
- Explicit commands act immediately
- Use `click.echo()` never `print()`
- Support `--json` flag where appropriate

### File I/O
- Use `pathlib.Path` exclusively
- Prefer atomic operations for lock/state files
- Specify `encoding='utf-8'` for text files
- Keep state as plain text (INI, JSON, key=value)

### Subprocess Execution
- Use `subprocess.run()` for sync commands
- Use `subprocess.Popen()` for long-running processes
- Always check `returncode`
- Use list form for safety (no shell injection)

### JSON Contracts
- Define TypedDict or dataclasses for contracts
- Version schemas (top-level `"version": 1`)
- Use `sort_keys=True` for stable output
- No ANSI codes in `--json` output

### Testing
- Use `pytest`
- Use `tmp_path` fixture for temp files
- Test both success and failure paths
- Use descriptive test names
- Keep tests focused and independent

## Project Structure

```
village/
├── cli.py              # Click commands
├── config.py           # Config loading
├── locks.py            # Lock file handling
├── worktrees.py        # Git worktree management
├── queue.py            # Task queue scheduler
├── resume.py           # Resume logic
├── cleanup.py          # Cleanup ops
├── ready.py            # Readiness engine
├── status.py           # Status reporting
├── probes/             # Runtime probes
│   ├── tmux.py
│   ├── beads.py
│   └── repo.py
└── render/             # Output renderers
    ├── text.py
    └── json.py
tests/
└── test_*.py
```

## Key Integration Points

### tmux
- Pane IDs are authoritative (`%12`, `%13`)
- Use `tmux list-panes` to enumerate workers
- Use `tmux has-session` to check session existence
- Auto-name windows: `<agent>-<num>-<task-id>`

### Git Worktrees
- Worktrees in `.worktrees/`
- Named by task ID (`.worktrees/bd-a3f8/`)
- Always `git worktree prune` after deletion

### Beads
- Use `bd ready` to query task DAG
- Parse Beads ID format (`bd-xxxx`)
- Treat Beads as single source of truth for readiness

### OpenCode
- Run as subprocess in tmux pane
- Inject contract via stdin or file
- Worker = one tmux pane + one OpenCode instance

## Constraints

- **No daemon** - CLI commands only
- **No database** - file-based state only
- **No cloud** - local-only
- **No remote workers** - single machine
- **Text-based everything** - JSON, key=value, INI
- **Safe by default** - plan/dry-run before mutation
- **Truth over intention** - probe actual state

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **Evaluate version impact** - Review your changes and apply bump label:
   ```bash
   bd label add <task-id> bump:<type>
   ```
   
   | Type   | When to use                          |
   |--------|--------------------------------------|
   | major  | Breaking changes, API removal        |
   | minor  | New features, backwards-compatible   |
   | patch  | Bug fixes, small improvements        |
   | none   | Docs, tests, internal refactors      |
   
   Default mapping from scope: fix→patch, feature→minor, others→none.
   Override with explicit label if actual impact differs.
5. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd sync
   git push
   git status  # MUST show "up to date with origin"
   ```
6. **Clean up** - Clear stashes, prune remote branches
7. **Verify** - All changes committed AND pushed
8. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
