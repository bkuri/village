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

### ACP Testing
- **Server tests**: `tests/test_acp_server.py` - Village as ACP agent
- **Client tests**: `tests/test_acp_client.py` - Village as ACP client
- **Bridge tests**: `tests/test_acp_bridge.py` - Protocol translation
- **Integration tests**: `tests/test_acp_integration.py` - End-to-end flows
- **Fixtures**: `tests/fixtures/acp_fixtures.py` - Mock agents and clients

**Test commands:**
```bash
# Test ACP server
pytest tests/test_acp_server.py -v

# Test ACP client
pytest tests/test_acp_client.py -v

# Test bridge
pytest tests/test_acp_bridge.py -v

# Test integration
pytest tests/test_acp_integration.py -v

# Test all ACP
pytest tests/ -k acp -v
```

**Manual testing:**
```bash
# Start ACP server
village acp --server start

# Test agent connection
village acp --client test claude

# Spawn agent
village acp --client spawn claude

# Check status
village acp --server status
```

## Project Structure

```
village/
├── cli/                # CLI commands (role-based)
│   ├── planner.py      #   village planner — spec design + inspection
│   ├── builder.py      #   village builder — spec-driven autonomous loop
│   ├── scribe.py       #   village scribe — knowledge base + goals + audit trails
│   ├── council.py      #   village council — multi-persona deliberation
│   ├── greeter.py      #   village greeter — Q&A session
│   └── ...
├── config.py           # Config loading
├── roles.py            # RoleChat base, routing table, greetings
├── loop.py             # Spec-driven autonomous build loop
├── workflow/            # Workflow engine (planner infrastructure)
│   ├── schema.py       #   Step types, WorkflowSchema
│   ├── loader.py       #   YAML loader
│   ├── builder.py      #   Execution engine
│   ├── planner.py      #   LLM-driven design
│   └── mcp_tools.py    #   Perplexity/sequential-thinking
├── council/            # Council deliberation system
├── scribe/              # Scribe knowledge base + audit trails
├── onboard/            # Adaptive onboarding
├── goals.py            # Goal hierarchy (GOALS.md)
├── trace.py            # TraceWriter/Reader (JSONL)
├── builder_state.py    # Run state (manifest + step log)
├── memory.py           # MemoryStore (markdown + YAML frontmatter)
├── queue.py            # Task queue scheduler
├── state_machine.py    # Task lifecycle states
├── locks.py            # Lock file handling
├── probes/             # Runtime probes
└── render/             # Output renderers
workflows/              # Built-in workflow YAML files
personas/               # Council persona definitions
tests/
└── test_*.py
```

## Village Scribe — Knowledge Base & Audit Trails

### Commands
```bash
village scribe see <url|file>         # Ingest knowledge source
village scribe fetch <url|file>       # Alias for see
village scribe ask "question"         # Query knowledge base
village scribe curate                 # Health check + regenerate VOICE.md
village scribe upkeep                 # Alias for curate
village scribe stats                  # Show wiki statistics
village scribe monitor                # Watch wiki/ingest/ for new files
village scribe goals                  # Show goal hierarchy
village scribe goals --coverage       # Show objective completion %
village scribe goals --edit           # Interactive refinement
village scribe goals --json           # JSON output
village scribe ledger show [task]     # View audit trail for a task
village scribe ledger list            # List tasks with traces
```

### Architecture
```
wiki/
├── ingest/              # Drop sources here
├── processed/           # Moved after ingestion
├── pages/               # Wiki pages (markdown + YAML frontmatter)
├── index.md             # Auto-generated catalog
└── log.md               # Chronological record

.village/memory/         # Agent cross-session memory (same format)
VOICE.md                 # Distilled project knowledge for agents
```

### Village Voice
Current project knowledge is maintained in `VOICE.md` at the repository root.
Read it first for project context, conventions, and known issues.

### Manual testing
```bash
village scribe see ./docs/guide.md
village scribe see https://docs.example.com/api
village scribe ask "how do I configure auth?"
village scribe curate
village scribe stats
village scribe ledger show bd-xyz
```

## Adaptive Onboarding

### Commands
```bash
village new <name>                # Create project with adaptive interview
village new <name> --skip-onboard # Create with minimal templates
village up                        # Detects incomplete setup, runs interview if needed
village up --skip-onboard         # Skip onboarding check
village onboard                   # Force-run onboarding on existing project
village onboard --force           # Overwrite existing AGENTS.md/README.md
village onboard --skip-interview  # Use scaffold defaults without interview
```

### Configuration
```ini
[onboard]
interview_model = openrouter/auto
max_questions = 15
critic_persona = red-team        # devil's-advocate | red-team | gordon-ramsay
self_critique = true
```

### Architecture
The onboarding pipeline:
1. **Detect** (rule-based): Scan for pyproject.toml, package.json, etc.
2. **Interview** (LLM adaptive): 10-15 BRUTAL-method questions
3. **Generate**: AGENTS.md + README.md + wiki/ seeds
4. **Process**: Scribe ingests wiki seeds, curate generates VOICE.md

## Role-Based CLI Architecture

### Planner Produces Specs, Builder Implements Specs

| Role | Default Chat | Subcommands |
|------|-------------|-------------|
| **planner** | "What do you want to accomplish?" | `workflows`, `show`, `design`, `refine`, `inspect` |
| **builder** | "Which specs shall I work on?" | `run`, `status`, `stop`, `resume`, `logs` |
| **scribe** | "What do you want to know?" | `see`, `ask`, `curate`, `goals`, `stats`, `ledger show`, `ledger list` |
| **council** | "What shall we discuss?" | `debate`, `list`, `show`, `rematch` |
| **doctor** | "What seems to be the problem?" | `check` |
| **greeter** | "How can I help?" | General triage, routes to all roles |

### Spec-Driven Build Loop

The builder implements specs autonomously via the Ralph Wiggum methodology.

```bash
# Planning — decides what, produces specs
village planner design <goal>          # LLM pipeline → produces spec in specs/
village planner inspect                # Review all specs (read-only)
village planner inspect --fix          # Review + amend specs with Inspect Notes
village planner inspect <spec-id>      # Review one spec
village planner refine <spec-id>       # Iterate on a spec

# Building — implements specs via autonomous loop
village builder run                    # Loop through specs (sequential, 1 worktree)
village builder run -p 4               # Parallel mode, 4 worktrees
village builder run -n 20              # Max 20 iterations
village builder run -m zai/glm-5-turbo # Override agent model
village builder run --dry-run          # Preview without executing
village builder status                 # Show spec completion progress
village builder stop                   # Halt the loop
village builder resume                 # Resume a stopped loop
village builder logs                   # View iteration logs
```

### Spec Format

Specs are numbered markdown files in `specs/`:

```markdown
# 001-core-config

## Overview
Core configuration and CLI framework.

## Status: incomplete

## Requirements
- FR-1: Load config from INI files
  - [ ] Parses `.village/config` correctly
  - [ ] Falls back to defaults

## Completion Signal
Run `village doctor check` and verify all pass.
<promise>DONE</promise>
```

- **Priority**: Lexicographic filename order (001, 002, ...)
- **Completion**: `Status: COMPLETE` written by the agent when done
- **Promise signal**: Agent outputs `<promise>DONE</promise>` when all criteria met
- **Inspect Notes**: Appended by `planner inspect --fix`, treated as hard constraints

### Cross-Role Routing

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

### ACP Integration
- **Server mode**: Village exposes ACP interface for editors (Zed, JetBrains)
- **Client mode**: Village spawns external ACP agents (Claude Code, Gemini CLI)
- **Bridge**: `village/acp/bridge.py` translates ACP ↔ Village operations
- **Configuration**: `[acp]` section in `.village/config` and `type=acp` agents
- **Testing**: Use `village acp --client test <agent-name>` to verify connections
- **Commands**: See `village acp --help` for server/client operations

**CLI Commands:**
```bash
# Server operations
village acp --server start [--host HOST] [--port PORT]
village acp --server stop
village acp --server status

# Client operations
village acp --client list
village acp --client spawn <agent-name>
village acp --client test <agent-name>
```

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

   **ENFORCEMENT**: `village release` will BLOCK if any closed task has no bump label.
   Every task — including docs-only changes — MUST have a bump label before release.
   Use `bump:none` for tasks with no version impact. Use `--force` only in emergencies.
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

<!-- BEGIN BEADS INTEGRATION -->
## Issue Tracking with bd (beads)

**IMPORTANT**: This project uses **bd (beads)** for ALL issue tracking. Do NOT use markdown TODOs, task lists, or other tracking methods.

### Why bd?

- Dependency-aware: Track blockers and relationships between issues
- Git-friendly: Dolt-powered version control with native sync
- Agent-optimized: JSON output, ready work detection, discovered-from links
- Prevents duplicate tracking systems and confusion

### Quick Start

**Check for ready work:**

```bash
bd ready --json
```

**Create new issues:**

```bash
bd create "Issue title" --description="Detailed context" -t bug|feature|task -p 0-4 --json
bd create "Issue title" --description="What this issue is about" -p 1 --deps discovered-from:bd-123 --json
```

**Claim and update:**

```bash
bd update <id> --claim --json
bd update bd-42 --priority 1 --json
```

**Complete work:**

```bash
bd close bd-42 --reason "Completed" --json
```

### Issue Types

- `bug` - Something broken
- `feature` - New functionality
- `task` - Work item (tests, docs, refactoring)
- `epic` - Large feature with subtasks
- `chore` - Maintenance (dependencies, tooling)

### Priorities

- `0` - Critical (security, data loss, broken builds)
- `1` - High (major features, important bugs)
- `2` - Medium (default, nice-to-have)
- `3` - Low (polish, optimization)
- `4` - Backlog (future ideas)

### Workflow for AI Agents

1. **Check ready work**: `bd ready` shows unblocked issues
2. **Claim your task atomically**: `bd update <id> --claim`
3. **Work on it**: Implement, test, document
4. **Discover new work?** Create linked issue:
   - `bd create "Found bug" --description="Details about what was found" -p 1 --deps discovered-from:<parent-id>`
5. **Complete**: `bd close <id> --reason "Done"`

### Auto-Sync

bd automatically syncs via Dolt:

- Each write auto-commits to Dolt history
- Use `bd dolt push`/`bd dolt pull` for remote sync
- No manual export/import needed!

### Important Rules

- ✅ Use bd for ALL task tracking
- ✅ Always use `--json` flag for programmatic use
- ✅ Link discovered work with `discovered-from` dependencies
- ✅ Check `bd ready` before asking "what should I work on?"
- ❌ Do NOT create markdown TODO lists
- ❌ Do NOT use external issue trackers
- ❌ Do NOT duplicate tracking systems

For more details, see README.md and docs/QUICKSTART.md.

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd sync
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds

<!-- END BEADS INTEGRATION -->

## Changelog Management

**All notable changes are documented in CHANGELOG.md following [Keep a Changelog](https://keepachangelog.com/).**

### Categorization

Changes are automatically categorized during `village release` based on task metadata:

- **Added**: New features (`feature` tasks in Beads)
- **Changed**: Enhancements, refactors (`task`/`chore` tasks)
- **Fixed**: Bug fixes (`bug` tasks)
- **Breaking**: Breaking changes (tasks with `bump:major` label)

### During Development

When completing a task:

1. **Apply bump label**: `bd label add <task-id> bump:<type>`
   - `major` for breaking changes
   - `minor` for new features
   - `patch` for bug fixes
   - `none` for docs/tests/internal work
2. **Ensure task title is clear and user-facing** (will appear in changelog)
   - ✅ "Add retry logic to queue processing"
   - ✅ "Fix deadlock in lock acquisition"
   - ❌ "Refactor _internal_helper function"
3. **Close task**: `bd close <task-id> --reason "Completed"`

### During Release

`village release` automatically:

1. Queries Beads for task types
2. Groups closed tasks by changelog category
3. Updates CHANGELOG.md with new version section
4. Creates git tag

**No manual changelog editing required.**

### Example Changelog Entry

```markdown
## [1.2.0] - 2026-03-11

### Breaking
- Remove deprecated `--old-flag` CLI option (`bd-a3f8`)

### Added
- Automatic task decomposition with LLM analysis (`bd-b4c9`)
- Extensibility framework for custom processors (`bd-d2e7`)

### Fixed
- Beads CLI compatibility with missing `--status` flag (`bd-c1d6`)

### Changed
- Improved error messages for lock conflicts (`bd-e5f2`)
```

### Edge Cases

- **Missing task type**: Defaults to "Changed" category
- **Beads unavailable**: Gracefully falls back to generic categorization
- **Empty categories**: Skipped in final changelog entry
- **bump:none tasks**: Excluded from changelog entirely
