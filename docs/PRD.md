# Village PRD - v1.0

## Purpose

Village is a **CLI-native parallel development orchestrator** built on:

- **Beads** - Task DAG and readiness
- **tmux** - Execution runtime and observability
- **git worktrees** - Isolation
- **OpenCode** - Agent execution
- **ppc** - Deterministic contract generation

Village is intentionally:

- Daemonless
- State-light
- Text-based
- Fully inspectable
- Safe by default

---

## Design Principles

1. **No surprises**
   - Ambiguous commands default to planning mode
   - Explicit commands perform actions
2. **Truth over intention**
   - tmux pane IDs are authoritative runtime handle
3. **One source of readiness**
   - `bd ready` → work readiness
   - `village ready` → execution readiness
4. **Separation of concerns**
   - `ready` interprets
   - `status` reports
   - `queue/resume` act
5. **Everything scriptable**
   - JSON output is first‑class API

---

## Village vs OpenCode + PPC: Why Village Exists

### Village's Unique Value Proposition

Village is **coordination infrastructure**, not just "OpenCode with policies".

**What OpenCode + PPC provides:**
- Static prompt generation via PPC
- Isolated execution via OpenCode
- No coordination between sessions
- No persistent state
- No recovery model

**What Village provides (and OpenCode cannot):**

| Capability | Village | OpenCode + PPC | Why Village is Essential |
|------------|---------|----------------|-------------------------|
| Multi-agent coordination | ✅ Lock system, concurrency limits | ❌ No coordination | Prevents duplicate work, enforces fairness |
| State management | ✅ Lock files, event logs | ❌ No persistent state | Enables crash recovery, audit trails |
| Runtime policies | ✅ Deduplication, resource limits | ❌ Static prompts only | Adapts to runtime conditions |
| Observability | ✅ Status system, event logging | ❌ No visibility | Debugging, monitoring, trust |
| Recovery model | ✅ Orphan detection, cleanup | ❌ No recovery | Survives crashes, interruptions |
| Conflict detection | ✅ File overlap detection | ❌ No conflict handling | Prevents resource corruption |
| Beads integration | ✅ DAG-aware scheduling | ❌ Manual task selection | Optimal task ordering |
| tmux orchestration | ✅ Session/pane lifecycle | ❌ Manual session mgmt | Consistent runtime behavior |

### The "Local, Auditable" Advantage

**Village runs as a local service with auditable source code:**
- Source code can be inspected and verified
- Log files capture exact execution paths
- Stack traces trace through local code
- Tests guarantee behavior (deterministic, reproducible)
- No black-box decisions (every operation is explainable)

**Contrast with LLM-only approaches:**
- LLMs are black boxes (cannot inspect reasoning)
- Cannot guarantee what happened vs what should happen
- No source code to review or audit
- Behavior may be non-deterministic
- Cannot trust execution without transparency

**This matters because:**
- **Security**: Local code can be audited; LLMs cannot
- **Debugging**: Stack traces point to exact line; LLM outputs do not
- **Reproducibility**: Same input → same output; LLMs may vary
- **Trust**: You can verify Village's source code; you cannot verify an LLM
- **Compliance**: Audit trails require verifiable source code

### Village's Role in the Toolchain

```
┌─────────────────────────────────────────────────────────────┐
│ Intent Plane (What to do)                               │
│ • Beads: Task DAG, readiness, dependencies             │
│ • PPC: Prompt generation (optional)                     │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Coordination Plane (How to coordinate)                 │
│ • Village: Scheduling, locking, policies, recovery      │
│   → Multi-agent coordination (impossible without Village)  │
│   → Stateful orchestration (OpenCode cannot provide)     │
│   → Safety guarantees (LLMs cannot guarantee)            │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Execution Plane (Do the work)                           │
│ • tmux: Runtime truth, observability                    │
│ • git/jj worktrees: Isolation                         │
│ • OpenCode: Agent execution                             │
└─────────────────────────────────────────────────────────────┘
```

**Village is indispensable because:**
- OpenCode cannot coordinate (runs isolated sessions)
- PPC cannot execute (generates static prompts)
- LLMs cannot guarantee safety (black boxes)
- Village provides the coordination layer that transforms isolated OpenCode sessions into a managed multi-agent workforce

**Without Village, you cannot reliably:**
1. Run multiple agents in parallel without conflicts
2. Survive crashes without losing work
3. Prevent duplicate task execution
4. Observe what's actually running across all sessions
5. Clean up orphaned resources
6. Scale to production workloads with guarantees

**Village's core differentiator**: Not execution (OpenCode does that), not prompts (PPC does that), but **coordination infrastructure** with audit trails, safety guarantees, and production reliability.

---

## Core Concepts

### Task

- Identified by Beads ID (`bd-xxxx`)
- Has dependencies and readiness

### Worker

- One tmux pane
- One OpenCode instance
- One claimed task

### Lock

- File-backed lease
- Stores tmux pane ID
- ACTIVE if pane exists
- STALE otherwise

### Orphans

- Stale locks (panes that no longer exist)
- Untracked worktrees (no corresponding lock)

### SCM Abstraction

Village uses a pluggable SCM (Source Control Management) layer for workspace operations:

**Supported SCMs:**
- Git (current, v1.0)
- Jujutsu (jj) - Planned for v2

**SCM Protocol:**
- `ensure_repo()` - Verify repository exists
- `check_clean()` - Check for uncommitted changes
- `ensure_workspace()` - Create/update workspace
- `remove_workspace()` - Delete workspace
- `list_workspaces()` - List all workspaces

**Configuration:**
```ini
[DEFAULT]
SCM=git
```

Environment variable: `VILLAGE_SCM=git|jj`

This design enables:
- Future jj backend without core logic changes
- Custom SCM backends
- Core Village logic remains SCM-agnostic

---

## Command Surface

### Runtime Lifecycle

```bash
village up [--dry-run|--plan] [--no-dashboard]
village down [--dry-run|--plan]
```

### Work Execution

```bash
village resume <id> [agent] [--detached] [--html] [--dry-run]
village resume  # Planner mode (no args)
village queue [--n N] [agent] [--dry-run|--plan] [--max-workers N] [--json]
```

### Read-Only Inspection

```bash
village ready [--json]
village status [--short|--workers|--locks|--orphans|--json]
village drafts [--scope <type>] [--total]
```

### Maintenance

```bash
village cleanup [--dry-run|--plan]
village unlock <id> [--force]
village locks
```

### Conversational Interface

```bash
village chat [--create] [--force]
```

---

## Command Semantics

### village up

Mutating. Idempotent.

Ensures:
- `.village/` directory structure
- `.village/config` with defaults
- `.village/locks/` directory
- `.worktrees/` directory
- Beads initialized (if available)
- tmux session exists
- Dashboard window created (optional, default enabled)

Does **not** start workers.

Supports: `--dry-run`, `--plan`, `--no-dashboard`

### village down

Stops tmux session only.

Leaves worktrees and locks intact (use `cleanup` to remove).

Supports: `--dry-run`, `--plan`

### village ready

Non-mutating.

Answers: "Is this environment ready to execute work?"

Reports:
- Environment readiness (git repo)
- Runtime readiness (tmux session)
- Orphan detection (stale locks, untracked worktrees)
- Work availability (ready tasks from Beads)
- Suggested actions

Supports: `--json`

Never mutates state.

### village status

Non-mutating. Pure inspection.

Flags:
- `--short`: Minimal status (tmux + locks count)
- `--workers`: Tabular workers view (TASK_ID, STATUS, PANE, AGENT, WINDOW)
- `--locks`: All locks with ACTIVE/STALE status
- `--orphans`: Orphaned resources with suggested actions
- `--json`: Full status as JSON

No recommendations by default.

### village resume <id>

Explicit action.

- Resumes specific task
- Creates or reuses worktree
- Creates tmux window
- Captures pane ID
- Writes lock file
- Starts OpenCode
- Injects contract

Acts immediately.

Options:
- `--agent <name>`: Use specific agent (auto-detect from Beads if not provided)
- `--detached`: Run without attaching to tmux pane
- `--html`: Output HTML with embedded JSON metadata
- `--dry-run`: Preview mode (no mutations)

### village resume (no id)

Planner mode. Prints recommended next action.

Decision order:
1. Ensure runtime via `village up`
2. Attach if active workers exist
3. Cleanup if stale locks exist
4. Queue ready tasks if available
5. Otherwise show `village ready` summary

### village queue

Explicit scheduler.

- Consumes `bd ready`
- Skips ACTIVE locks
- Steals STALE locks
- Auto-names windows (`<agent>-<num>-<task-id>`)
- Uses detached mode
- Respects concurrency limits

Supports: `--dry-run`, `--plan`, `--n <count>`, `--agent <name>`, `--max-workers N`, `--json`

### village cleanup

Housekeeping command.

Default scope: Remove stale locks only.

Future scope: Worktree pruning behind flags.

Supports: `--dry-run`, `--plan`

### village unlock

Unlock a task (remove lock file).

Safety check: Verifies pane is not ACTIVE unless `--force` is provided.

### village chat

Conversational interface for knowledge sharing and task creation.

Modes:
- Knowledge-share (default): Clarify project understanding, document decisions
- Task-create (`--create`): Define structured tasks for Beads

Subcommands (read-only):
- `/tasks`, `/task <id>`, `/ready`, `/status`, `/help`
- `/create`, `/enable`, `/edit`, `/discard`, `/submit`, `/drafts` (task-create only)

All outputs are markdown files in `.village/context/`.

---

## Lock File Schema

```
id=bd-a3f8
pane=%12
window=build-1-bd-a3f8
agent=build
claimed_at=2026-01-22T10:41:12
```

Pane ID is authoritative lease handle.

---

## JSON Contract

All JSON output:
- Valid JSON only
- No ANSI codes
- Stable keys
- Versioned schema

Top-level example (ready command):

```json
{
  "command": "ready",
  "version": 1,
  "assessment": {
    "overall": "ready",
    "environment_ready": true,
    "runtime_ready": true,
    "work_available": "available",
    "orphans_count": 0,
    "stale_locks_count": 0,
    "untracked_worktrees_count": 0,
    "active_workers_count": 0,
    "ready_tasks_count": 3,
    "error": null
  }
}
```

---

## Exit Codes

| Code | Meaning | Example |
|------|---------|---------|
| 0 | Success | `village resume bd-a3f8` completes |
| 1 | Generic error | Worktree creation failed |
| 2 | Not ready / precondition failed | Repository not initialized |
| 3 | Blocked / no work available | `village queue` with no ready tasks |
| 4 | Partial success | `village queue` with some tasks failed |
| 5 | Invalid usage | Missing required arguments |

---

## Module Layout

```
village/
  cli.py                 # CLI entrypoint
  config.py              # Configuration loader
  contracts.py           # Contract generation
  errors.py             # Exception hierarchy + exit codes
  locks.py              # Lock file handling
  worktrees.py          # Workspace management via SCM abstraction
  queue.py              # Task queue scheduler
  resume.py             # Resume logic + planner
  cleanup.py            # Cleanup operations
  ready.py              # Readiness engine
  status.py             # Status reporting
  logging.py            # Logging setup
  opencode.py           # OpenCode integration
  ppc.py                # PPC integration (optional)
  runtime.py            # Runtime lifecycle
  agents.py             # Agent configuration
  scm/                  # SCM abstraction layer (v1.1)
    protocol.py         # SCM Protocol interface
    utils.py            # Common workspace utilities
    git.py              # GitSCM backend implementation
  probes/               # Runtime probes
    tmux.py             # Tmux session/pane queries
    beads.py            # Beads availability
    repo.py             # Git repository detection
    tools.py            # Subprocess wrapper
    ppc.py              # PPC availability
  render/               # Output renderers
    text.py             # Text output
    json.py             # JSON output
    html.py             # HTML output
    colors.py           # Color helpers
  chat/                 # Conversational interface
    conversation.py      # Conversation state
    state.py            # Session persistence
    prompts.py          # Chat prompts
    drafts.py           # Draft task management
    schema.py           # Draft data structures
    context.py          # Context file management
    subcommands.py      # Chat subcommands
    errors.py           # Chat-specific errors
```

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `VILLAGE_DIR` | Village directory path | `.village/` |
| `VILLAGE_WORKTREES_DIR` | Worktrees directory | `.worktrees/` |
| `VILLAGE_MAX_WORKERS` | Max parallel workers | 2 |
| `VILLAGE_DEFAULT_AGENT` | Default agent name | `worker` |
| `VILLAGE_SESSION` | Tmux session name | `village` |

### Config File (.village/config)

INI-style config for agent configuration and SCM selection:

```ini
[DEFAULT]
DEFAULT_AGENT=worker
MAX_WORKERS=2
SCM=git

[agent.build]
opencode_args=--mode patch --safe
contract=contracts/build.md
ppc_mode=build
ppc_traits=conservative,terse
ppc_format=markdown

[agent.frontend]
opencode_args=--mode patch
contract=contracts/frontend.md
ppc_mode=explore
ppc_traits=verbose
ppc_format=markdown
```

### PPC Integration (Optional)

If `ppc` is installed, Village can generate contracts automatically.

Priority order:
1. Custom contract file (if specified)
2. PPC-generated prompt (if available)
3. Fallback Markdown template

If PPC is unavailable, Village falls back to Markdown templates.

---

## Non-Goals

- Background daemon
- Persistent database
- Cloud coordination
- Remote workers
- GUI
- YAML workflows
- Plugin marketplaces

Village remains a **local-first flow engine**.

---

## Audit & Trust Guarantees

### Local, Auditable Source Code

Village runs as a **local service with auditable source code**:

- Source code can be inspected and verified
- Log files capture exact execution paths
- Stack traces trace through local code
- Tests guarantee behavior (deterministic, reproducible)
- No black-box decisions (every operation is explainable)

### Audit Trail Features

**Event Logging**:
- All operations logged to `.village/events.log` (NDJSON format)
- Each entry includes: timestamp, command, task_id, pane_id, result
- Stack traces captured for errors
- Source code version included in log entries

**State Inspection**:
- Lock files provide persistent lease records
- Worktree status can be queried
- Tmux pane IDs prove what's actually running
- Orphan detection identifies incomplete operations

**Deterministic Behavior**:
- Same inputs → same outputs
- No hidden randomization or non-determinism
- Version-controlled contracts and policies
- Test suite validates expected behavior

### Contrast with LLM-Only Approaches

**LLM Limitations**:
- Black box reasoning (cannot inspect decision process)
- No source code to review or audit
- Behavior may be non-deterministic
- Cannot verify what happened vs what should happen
- No stack traces or error context

**Village Advantages**:
- ✅ Local, auditable source code
- ✅ Complete audit trails (event logs, stack traces)
- ✅ Deterministic, reproducible behavior
- ✅ Test guarantees for all operations
- ✅ Every operation is explainable

**This matters because**:
- **Security**: Local code can be audited; LLMs cannot
- **Debugging**: Stack traces point to exact line; LLM outputs do not
- **Reproducibility**: Same input → same output; LLMs may vary
- **Trust**: You can verify Village's source code; you cannot verify an LLM
- **Compliance**: Audit trails require verifiable source code

### Production Trust Model

Village establishes a **trust model based on verifiability**:

1. **You can verify**: Source code is open and inspectable
2. **You can audit**: Event logs capture every operation
3. **You can reproduce**: Deterministic behavior yields consistent results
4. **You can debug**: Stack traces show exact execution paths

This is fundamentally different from LLM-only approaches where:
- Reasoning is opaque (black box)
- Behavior is variable (non-deterministic)
- No audit trail (just inputs and outputs)
- Cannot verify correctness (trust without verification)

---

## Success Criteria for v1.0

Village v1.0 is production-ready when:

### Critical Differentiators (v0.3.0)

1. **Coordination Infrastructure**
   - [ ] Multiple agents run in parallel without conflicts
   - [ ] Concurrency limits are enforced across all agents
   - [ ] Priority-based scheduling works correctly (if implemented)
   - [ ] Resource quotas prevent resource exhaustion (if implemented)

2. **State Management**
   - [ ] Lock files survive crashes and are recoverable
   - [ ] Orphan detection identifies incomplete operations
   - [ ] Event logs provide complete audit trails
   - [ ] State machine transitions are validated
   - [ ] Session snapshots enable rollback capability

3. **Safety & Recovery**
   - [ ] Automatic rollback recovers from failed tasks
   - [ ] Conflict detection prevents data corruption
   - [ ] Cleanup automation removes orphaned resources
   - [ ] Deduplication prevents duplicate work

### Observability (v0.4.0)

4. **System Visibility**
   - [ ] Real-time dashboard shows system state
   - [ ] Metrics export integrates with monitoring tools (Prometheus, StatsD)
   - [ ] Event queries provide historical inspection
   - [ ] Status commands report complete system state

5. **Audit & Trust**

6. **Audit Trails**
   - [ ] All operations are logged with stack traces
   - [ ] Source code is auditable and verifiable
   - [ ] Tests guarantee deterministic behavior
   - [ ] No black-box decisions (everything is explainable)

7. **Local, Auditable Guarantee**
   - [ ] README and PRD emphasize local service advantage
   - [ ] Documentation explains audit features
   - [ ] Source code version in log entries
   - [ ] Deterministic behavior documented

### Production Readiness

8. **Quality & Stability**
   - [ ] Test coverage >85% overall, >90% for critical modules
   - [ ] Zero critical bugs (exit code 1 crashes)
   - [ ] All features documented with examples
   - [ ] Troubleshooting guide comprehensive
   - [ ] CHANGELOG.md comprehensive and up-to-date

9. **Integration & Completeness**
   - [ ] GitHub integration works correctly (if implemented)
   - [ ] CI/CD triggers execute on task completion (if implemented)
   - [ ] Notifications sent for configured events (if implemented)
   - [ ] Beads sync keeps task status updated
   - [ ] Multi-repo support works (if implemented)

10. **User Experience**
    - [ ] E2E test suite passes (>30 tests) (v1.1.0 milestone)
    - [ ] All commands work identically across SCM backends (git, jj)
    - [ ] Zero breaking changes from v0.2.x to v1.0.0
    - [ ] Error messages are actionable and specific
    - [ ] Migration guide provided (v0.2.x → v1.0.0)

### v1.0.0 Release Checklist

**Essential Features (v0.3.0-v0.4.0):**
- [ ] State machine workflows implemented and working
- [ ] Automatic rollback functional
- [ ] Conflict detection operational
- [ ] Real-time dashboard functional
- [ ] Metrics export working
- [ ] Event queries operational

**Production Readiness:**
- [ ] Test coverage >85% overall
- [ ] Zero critical bugs in production
- [ ] Documentation complete (README, PRD, examples, troubleshooting)
- [ ] CHANGELOG.md up-to-date
- [ ] Audit trails comprehensive

**Quality Assurance:**
- [ ] E2E test suite passing (>30 tests, v1.1.0)
- [ ] All features tested end-to-end
- [ ] Backward compatibility verified
- [ ] Performance benchmarks documented

---

## Version History

- **v0.2.3** (Current) - Jujutsu (jj) support
- **v0.3.0** (Planned) - Safety & coordination (essential)
- **v0.4.0** (Planned) - Enhanced observability (essential)
- **v1.0.0** (Target) - Production-ready coordination layer
- **v1.1.0** (Future) - High-ROI integrations
- **v1.2.0** (Future) - Medium-ROI optimizations
- **v1.3.0** (Future) - Low-ROI features
