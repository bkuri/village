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
- Use `pytest` with `tmp_path` fixture
- Test both success and failure paths
- Keep tests focused and independent
- ACP tests: `tests/test_acp_*.py` + `tests/fixtures/acp_fixtures.py`

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
│   ├── scribe.py       #   village scribe — knowledge base
│   ├── council.py      #   village council — multi-persona deliberation
│   ├── watcher.py      #   village watcher — observability and maintenance
│   ├── doctor.py       #   village doctor — diagnostics
│   ├── greeter.py      #   village greeter — Q&A session
│   ├── goals.py        #   village goals — goal hierarchy
│   ├── lifecycle.py    #   new, up, down
│   ├── acp.py          #   village acp — agent bridge
│   ├── tasks.py        #   village tasks — task store management
│   ├── state.py        #   (logic-only, no CLI decorators)
│   ├── dashboard.py    #   (logic-only, no CLI decorators)
│   ├── maintenance.py  #   (logic-only, no CLI decorators)
│   ├── work.py         #   (logic-only, no CLI decorators)
│   └── release.py      #   (logic-only, no CLI decorators)
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

## Village Scribe — Knowledge Base

### Commands
```bash
village scribe fetch <url|file>       # Ingest knowledge source
village scribe ask "question"         # Query knowledge base
village scribe curate                 # Health check + regenerate VOICE.md
village scribe drafts                 # List or count draft tasks
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
village scribe fetch ./docs/guide.md
village scribe fetch https://docs.example.com/api
village scribe ask "how do I configure auth?"
village scribe curate
```

## Adaptive Onboarding

### Commands
```bash
village new <name>                # Create project with adaptive interview
village new <name> --skip-onboard # Create with minimal templates
village up                        # Detects incomplete setup, runs interview if needed
village up --skip-onboard         # Skip onboarding check
village up --force                # Overwrite existing AGENTS.md/README.md
village up --skip-interview       # Use scaffold defaults without interview
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
| **watcher** | "What would you like to observe?" | `status`, `locks`, `events`, `dashboard`, `cleanup`, `unlock`, `monitor`, `ledger show`, `ledger list`, `ready` |
| **builder** | "Which specs shall I work on?" | `run`, `status`, `cancel`, `logs`, `resume`, `queue`, `pause`, `release` |
| **scribe** | "What do you want to know?" | `fetch`, `ask`, `curate`, `drafts` |
| **planner** | "What do you want to accomplish?" | `workflows`, `show`, `design`, `refine`, `inspect` |
| **council** | "What shall we discuss?" | `debate`, `list`, `show` |
| **doctor** | "What seems to be the problem?" | `diagnose`, `prescribe` |
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
village builder run                    # Loop through specs
village builder run -p 4               # Parallel mode, 4 worktrees
village builder run -n 20              # Max 20 iterations
village builder run -m zai/glm-5-turbo # Override agent model
village builder run --dry-run          # Preview without executing
village builder status                 # Show spec completion progress
village builder cancel                 # Halt the loop
village builder resume --build         # Resume a stopped build loop
village builder resume --task <id>     # Resume a paused task
village builder queue                  # Queue and execute ready tasks
village builder pause                  # Pause an in-progress task
village builder release                # Ship a release
village builder logs                   # View iteration logs
```

### Village Watcher — Observability & Maintenance

```bash
village watcher status                # General overview
village watcher status --system       # System health (workers, locks, orphans)
village watcher status --task <id>    # Task state and history
village watcher status --wiki         # Wiki statistics
village watcher locks                 # List all locks
village watcher events                # Show recent events
village watcher dashboard             # Real-time dashboard
village watcher cleanup               # Remove stale locks/worktrees
village watcher unlock                # Unlock a task
village watcher monitor               # Watch wiki/ingest/ for new files
village watcher ledger show [task]    # View audit trail
village watcher ledger list           # List tasks with audit trails
village watcher ready                 # Readiness assessment
```

### Village Doctor — Diagnostics

```bash
village doctor diagnose               # Run full diagnostics (writes .village/diagnosis.json)
village doctor prescribe              # Show recommendations from diagnosis
village doctor prescribe --fix        # Auto-apply fixes
```

### Village Council — Deliberation

```bash
village council debate "topic"                    # Start a new debate
village council debate --from <id>                # Continue a past debate
village council debate --from <id> --rematch      # Re-run from scratch
```

### Spec Format

Specs: numbered markdown in `specs/` with `Status: incomplete` → `Status: COMPLETE`
- Use `<promise>DONE</promise>` when criteria met
- Priority by filename order (001, 002, ...)
- **Inspect Notes**: Appended by `planner inspect --fix`, treated as hard constraints

### Top-Level Commands
```bash
village new <name>                # Create project with adaptive interview
village up                        # Initialize village (includes onboarding)
village down                      # Stop village runtime
village goals                     # Show goal hierarchy
village tasks                     # Task store management
village acp                       # ACP agent bridge
village greeter                   # Interactive Q&A (aliases: welcome, chat, help)
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

### Village Tasks
- Use `village tasks ready` to query ready tasks
- Task IDs generated by Village's ID system
- Treat Village task store as source of truth for readiness

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

**When ending a work session in a Village-created project**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **Evaluate version impact** - Review your changes and apply bump label:
   ```bash
   village tasks label <task-id> add bump:<type>
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

<!-- BEGIN TASK STORE INTEGRATION -->
## Issue Tracking

**NOTE**: Village uses two separate task tracking systems:
- **Village task store** (`.village/tasks.jsonl`) - for projects created by Village
- **bd (Beads)** - for Village's own development (this repo)

### Village Task Store

For projects created by Village, use the built-in task store:

> **IMPORTANT**: This project uses the built-in **Village task store** for ALL issue tracking in Village-created projects. Do NOT use markdown TODOs, task lists, or external trackers.

### Architecture

The task store is a pluggable system with a JSONL file-based backend:

```
village/
├── tasks/
│   ├── models.py      # Task, TaskStatus, TaskType, TaskCreate, TaskUpdate
│   ├── store.py      # TaskStore abstract interface
│   ├── file_store.py # JSONL implementation
│   └── ids.py        # Task ID generation
.village/
└── tasks.jsonl      # Task persistence (one JSON per line)
```

### Task Statuses

- `open` - Ready to work, not yet claimed
- `draft` - Work not started, more definition needed
- `in_progress` - Currently being worked on
- `done` - Work completed, pending release
- `closed` - Released/versioned
- `deferred` - Blocked or postponed

### Task Types

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

### CLI Commands

```bash
village tasks list                    # List all tasks
village tasks list --status open     # Filter by status
village tasks list --type bug       # Filter by type
village tasks ready                # Show tasks ready to work on
village tasks get <id>             # Get task details
village tasks create "title" -t bug # Create new task
village tasks update <id> --status in_progress  # Claim/update
village tasks close <id> --reason "Completed"  # Close task
village tasks label <id> add bump:patch    # Add version label
```

### Dependencies

Tasks support dependency relationships:

- `blocks` / `blocked_by` - Blocker relationships
- `discovered-from` - Found while working on parent task

```bash
village tasks create "Subtask" --depends-on <parent-id>
village tasks depends <id> show
```

### Workflow for AI Agents

1. **Check ready work**: `village tasks ready` shows unblocked tasks
2. **Claim your task**: `village tasks update <id> --status in_progress`
3. **Work on it**: Implement, test, document
4. **Discover new work?** Create linked task:
   - `village tasks create "Found bug" --description="..." --depends-on <parent-id>`
5. **Complete**: `village tasks close <id> --reason "Done"`

### Important Rules

- ✅ Use `village tasks` for ALL issue tracking
- ✅ Always use `--json` for programmatic output
- ✅ Link discovered work with `--depends-on` 
- ✅ Check `village tasks ready` before asking "what should I work on?"
- ❌ Do NOT create markdown TODO lists
- ❌ Do NOT use external issue trackers
- ❌ Do NOT duplicate tracking systems

For more details, see `village tasks --help`.

### Village Development (Beads)

For Village's own development (this repo), use **bd (Beads)** instead:

> **IMPORTANT**: This is Village's own development repo. Use **bd** for issue tracking.

**Setup** (if not already initialized):
```bash
bd init
bd onboard
```

**Quick Start:**

```bash
bd ready                    # Show ready tasks
bd create "Title" -t bug      # Create new task
bd update <id> --claim      # Claim a task
bd close <id> --reason "Done"  # Complete work
```

**Auto-Sync:**
Beads syncs automatically - no manual push/pull needed.

### Important Rules

- ✅ Use bd for ALL task tracking in Village development
- ✅ Link discovered work with `discovered-from` dependencies
- ✅ Check `bd ready` before asking "what should I work on?"
- ❌ Do NOT use village tasks for this repo

<!-- END TASK STORE INTEGRATION -->

## Changelog Management

**All notable changes are documented in CHANGELOG.md following [Keep a Changelog](https://keepachangelog.com/).**

### Categorization

Changes are automatically categorized during `village release` based on task metadata:

- **Added**: New features (`feature` tasks)
- **Changed**: Enhancements, refactors (`task`/`chore` tasks)
- **Fixed**: Bug fixes (`bug` tasks)
- **Breaking**: Breaking changes (tasks with `bump:major` label)

### During Development

When completing a task:

1. **Apply bump label**: `village tasks label <task-id> add bump:<type>`
   - `major` for breaking changes
   - `minor` for new features
   - `patch` for bug fixes
   - `none` for docs/tests/internal work
2. **Ensure task title is clear and user-facing** (will appear in changelog)
   - ✅ "Add retry logic to queue processing"
   - ✅ "Fix deadlock in lock acquisition"
   - ❌ "Refactor _internal_helper function"
3. **Close task**: `village tasks close <task-id> --reason "Completed"`

### During Release

`village release` automatically queries task store for types, groups by changelog category, updates CHANGELOG.md, and creates git tag. No manual editing required.
