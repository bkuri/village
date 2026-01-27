# Village Roadmap

## Current Status: v0.3.0

### Implemented Core Features

- [x] **Phase 0-7**: Core Python implementation
  - [x] CLI entrypoint with Click
  - [x] Configuration system (env vars + INI file)
  - [x] Runtime probes (tmux, beads, repo)
  - [x] Lock system with ACTIVE/STALE detection
  - [x] Status system (workers, orphans, locks views)
  - [x] Readiness engine with suggested actions
  - [x] Runtime lifecycle (up, down, dashboard)
  - [x] Resume flow (explicit + planner modes)

- [x] **Phase 8**: Queue scheduler
  - [x] Ready task extraction from Beads
  - [x] Lock arbitration (skip ACTIVE, steal STALE)
  - [x] Auto window naming
  - [x] Concurrency limits
  - [x] Plan/dry-run modes

- [x] **Phase 9**: Contract system
  - [x] PPC detection and integration
  - [x] Agent → args mapping
  - [x] Fallback contracts
  - [x] Injection formatting

- [x] **Phase 10**: Hardening
  - [x] Error classification (Transient, Permanent, Config, UserInput)
  - [x] Exit codes (0-5)
  - [x] Interrupted execution recovery
  - [x] Corrupted lock handling

- [x] **Phase 11**: Polish
  - [x] Colored TTY output
  - [x] Shell completion (bash, zsh)
  - [x] Comprehensive README
  - [x] Examples and troubleshooting
  - [x] Migration notes from bash version

- [x] **Phase 12**: Chat interface
  - [x] Knowledge-share mode
  - [x] Task-create mode with drafts
  - [x] Context file management
  - [x] Read-only subcommands
  - [x] Session state persistence

### Current Statistics

- **Total Python LOC**: ~4,000 (exceeds 2k target due to chat feature)
- **Test Coverage**: >85% core commands, >90% resume flow
- **Commands Implemented**: 14 (up, down, status, ready, resume, queue, cleanup, unlock, locks, drafts, chat, state, pause, resume-task)

---

---

## v0.3.0 - Safety & Coordination (Essential) ✅

### Goal
Strengthen Village's core value as coordination layer - features OpenCode cannot provide.

### Scope

- [x] **State Machine Workflows**
  - **Task lifecycle states**: QUEUED → CLAIMED → IN_PROGRESS → PAUSED → COMPLETED → FAILED
  - **State transitions**: Validate and log all transitions
  - **New file**: `village/state_machine.py` (~200 lines)
  - **Commands**:
    ```bash
    village state bd-a3f8         # Show task state history
    village pause bd-a3f8         # Pause in-progress task
    village resume-task bd-a3f8   # Resume paused task
    ```

- [x] **Automatic Rollback on Failure**
  - **Worktree reset**: If task fails, revert worktree to clean state
  - **Lock update**: Mark task as FAILED in lock file
  - **Event logging**: Log rollback events to events.log
  - **Configuration**: `ROLLBACK_ON_FAILURE=true|false` (default: true)
  - **Integration**: Modify `resume.py` to wrap OpenCode execution in try/except

- [x] **Conflict Detection**
  - **File overlap detection**: Detect when agents modify same files
  - **Integration**: Check conflicts in `arbitrate_locks()` before claiming
  - **Warning**: `village queue --conflicts` shows potential conflicts
  - **Block on conflict**: Configurable `BLOCK_ON_CONFLICT=true|false`

### Design Decisions

1. **State machine as core coordination primitive**
   - Enables tracking task lifecycle
   - Validates state transitions (prevents invalid operations)
   - Supports pause/resume workflows

2. **Automatic rollback on failure**
   - Ensures clean recovery from errors
   - Prevents partial state corruption
   - User-controllable via config

3. **Conflict detection prevents data corruption**
   - Detects when agents modify same files
   - Blocks task execution if conflict detected
   - Configurable blocking (warn-only vs block)

### Files to Create/Modify

**New files:**
- `village/state_machine.py` (~200 lines)
- `village/conflict_detection.py` (~150 lines)

**Modified files:**
- `village/queue.py` (integrate conflict detection)
- `village/resume.py` (add rollback logic)
- `village/config.py` (add new config options)

**Test files to create:**
- `tests/test_state_machine.py`
- `tests/test_conflicts.py`

### Success Criteria

- [x] State machine transitions are validated and logged
- [x] Automatic rollback recovers from failed tasks
- [x] File conflicts detected before task execution
- [x] Test coverage >85% for new modules
- [x] Documentation updated (README, examples)

### Timeline Estimate

- **Total time**: 16-20 hours (spread over 2-3 weeks)
- **Phase breakdown**:
  - State machine design & implementation: 4-5 hrs
  - Rollback design & implementation: 3-4 hrs
  - Conflict detection design & implementation: 3-4 hrs
  - Config integration: 1 hr
  - Testing: 3-4 hrs
  - Documentation: 1-2 hrs

### Technical Notes

- State machine: Validate transitions, log all state changes to events.log
- Rollback: Use SCM commands to reset worktree (git reset, jj abandon)
- Conflict detection: Parse git/jj status, compare file sets across workers
- Event logging: All state changes and rollback attempts logged

---

## v0.4.0 - Enhanced Observability (Essential)

### Goal
Provide system-wide visibility that OpenCode cannot offer.

### Scope

- [x] **Real-Time Dashboard**
  - **New command**: `village dashboard --watch`
  - **Live display** (refresh every 2s):
    ```
    Active Workers (2/4)
    TASK_ID    STATUS    AGENT      PANE     WINDOW
    bd-a3f8    ACTIVE    build      %12      build-1-bd-a3f8
    bd-b7c2    ACTIVE    frontend   %13      frontend-1-bd-b7c2
    
    Task Queue (3 ready, 2 blocked)
    bd-c9d1 [READY]    high-priority
    bd-e4f2 [READY]    feature
    bd-f5g3 [READY]    fix
    
    Lock Status: 2 ACTIVE, 1 STALE, 0 orphans
    System Load: 2.3 / 8.0 (max workers: 4)
    ```
  - **Terminal UI**: Use rich.console or similar
  - **Interactive**: Press 'q' to quit, 'r' to refresh

 - [x] **Metrics Export**
   - **Backends**: Prometheus, StatsD, Custom
   - **New command**: `village metrics --backend prometheus`
   - **Metrics exposed**:
     - `village_active_workers` (gauge)
     - `village_queue_length` (gauge)
     - `village_stale_locks` (gauge)
     - `village_orphans_count` (gauge)
     - `village_task_completion_rate` (histogram)
     - `village_average_task_duration_seconds` (histogram)
   - **New file**: `village/metrics.py` (~200 lines)
   - **Configuration**:
     ```ini
     [metrics]
     backend=prometheus
     port=9090
     export_interval_seconds=60
     ```

- [x] **Structured Event Queries**
  - **New command**: `village events --task bd-a3f8 --last 1h --json`
  - **Filters**: `--task <id>`, `--status <STATUS>`, `--since <datetime>`, `--last <duration>`
  - **Output**: JSON or table format
  - **Integration**: Query `.village/events.log` with filtering
  - **New file**: `village/event_query.py` (~150 lines)

### Design Decisions

1. **Real-time dashboard for production monitoring**
   - Live visibility into system state
   - Refresh interval configurable (default: 2s)
   - Minimal dependencies (rich.console or similar)

2. **Metrics export integrates with existing monitoring stacks**
   - Prometheus and StatsD support for production environments
   - Custom backend option for other systems
   - Export interval configurable (default: 60s)

3. **Event queries enable historical analysis**
   - Filter by task, status, time range
   - JSON output for tooling integration
   - Table output for human readability

### Files to Create/Modify

**New files:**
- `village/dashboard.py` (~300 lines)
- `village/metrics.py` (~200 lines)
- `village/event_query.py` (~150 lines)

**Modified files:**
- `village/config.py` (add metrics/dashbard config)

**Test files to create:**
- `tests/test_dashboard.py`
- `tests/test_metrics.py`
- `tests/test_event_query.py`

### Success Criteria

- [x] Real-time dashboard displays live system state
- [x] Metrics export works for Prometheus and StatsD
- [x] Event queries filter and format correctly
- [x] Test coverage >80% for new modules
- [x] Documentation updated

### Timeline Estimate

- **Total time**: 12-16 hours (spread over 1-2 weeks)
- **Phase breakdown**:
  - Dashboard design & implementation: 4-5 hrs
  - Metrics design & implementation: 3-4 hrs
  - Event queries design & implementation: 2-3 hrs
  - Config integration: 1 hr
  - Testing: 2-3 hrs
  - Documentation: 1-2 hrs

### Technical Notes

- Dashboard: Use rich.console or similar terminal UI library
- Metrics: HTTP server for Prometheus scrape endpoint, UDP socket for StatsD
- Event queries: Parse NDJSON events.log, apply filters, output formatted results



### Goal
Formalize a critical architectural boundary: Village must not depend directly on Git semantics. Enable painless Jujutsu (jj) support without core logic refactoring.

### Scope

- [x] **SCM Interface Protocol**
  ```python
  class SCM(Protocol):
      kind: Literal["git", "jj"]

      def ensure_repo(repo_root: Path) -> None
      def check_clean(repo_root: Path) -> bool
      def ensure_workspace(repo_root: Path, workspace_path: Path, base_ref: str = "HEAD") -> None
      def remove_workspace(workspace_path: Path) -> bool
      def list_workspaces(repo_root: Path) -> list[WorkspaceInfo]
  ```

- [x] **Git Backend Implementation**
  - `village/scm/git.py`: GitSCM implements SCM Protocol
  - All Git commands isolated within GitSCM class
  - Maintains 100% backward compatibility
  - Uses Git porcelain format (`git worktree list --porcelain`)

- [x] **Workspace Model Refactoring**
  - Directory name encodes task ID (`.worktrees/bd-a3f8/`)
  - Directory is authoritative identity
  - SCM metadata irrelevant to Village core
  - `resolve_task_id()` extracts task ID from workspace path (Village-specific)

- [x] **Configuration Updates**
  ```ini
  [DEFAULT]
  SCM=git
  WORKTREES_DIR=.worktrees
  SESSION=village
  ```

  Environment variable: `VILLAGE_SCM=git|jj`

- [x] **Testing**
  - Unit tests for SCM Protocol interface
  - Unit tests for GitSCM backend
  - Integration tests verify backward compatibility
  - 294 tests passing (16 worktrees + 278 others)
  - Coverage: 64% overall, 100% for scm modules

### Success Criteria
- [x] Zero git commands outside `village/scm/git.py`
- [x] Core logic is SCM-agnostic
- [x] jj backend possible without core refactor
- [x] Codebase maintained (294 tests passing, full backward compatibility)

### Migration Notes
- No user-visible changes expected
- Existing worktrees and lock files remain compatible
- Git backend behavior is preserved
- All existing Village commands work identically



### Goal
Strengthen operational trust under heavy concurrency and frequent crashes. Make Village feel reliable even in production use.

### Scope

- [x] **Event Log (NDJSON)**
  - Append-only log at `.village/events.log`
  - Each action appends one JSON line:
    ```json
    {"ts":"2026-01-22T10:41:12","cmd":"queue","task":"bd-a3f8","pane":"%12","result":"ok"}
    ```
  - No indexing, no database, no rotation required
  - Uses: crash recovery inspection, deduplication, debugging

- [x] **Queue Deduplication Guard**
  - Consult `events.log` before starting tasks
  - Skip tasks started within configurable TTL (default: 5 minutes)
  - Override via `village queue --force`
  - Config: `QUEUE_TTL_MINUTES` or `VILLAGE_QUEUE_TTL_MINUTES` env var

- [x] **Expanded `--plan` Output**
  - `queue --plan --json` returns:
    - Tasks selected
    - Tasks skipped (with reason per task)
    - Locks involved (pane_id, window, agent, claimed_at)
    - Workspace paths
  - Enables dry-run scheduling validation

- [x] **Cleanup Enhancements**
  - `village cleanup --apply` removes orphan and stale worktrees
  - Safer corrupted lock handling via `parse_lock_safe()`
  - Separate orphan_worktrees and stale_worktrees in CleanupPlan

- [x] **Testing & Integration**
  - 58 new SCM tests (protocol compliance + Git backend + JJ placeholders)
  - 3 v1.2 integration tests (event logging, deduplication, cleanup)
  - Coverage: 74% overall (git.py: 85%, protocol: 100%)
  - E2E testing guidance added to ROADMAP

### Success Criteria

- [x] Users can trust `queue` under concurrency
- [x] Failures are explainable post-mortem
- [x] Shell scripts can reason via exit codes
- [x] No task accidentally runs twice

### Technical Notes

- Event log: village/event_log.py (78 lines)
- Deduplication: village/queue.py + village/config.py (TTL config)
- Cleanup: village/cleanup.py with --apply flag
- Tests: tests/test_event_log.py, tests/test_queue.py, tests/test_cleanup.py, tests/scm/test_*.py
- Coverage: 74% (2936 statements, 777 missed)
- Timezone handling: Fixed to use datetime.now(timezone.utc)

### Migration Notes

No migration required. All features backward compatible.

- Event logging: Automatic, no user action needed
- Queue deduplication: Opt-in via --force flag
- Cleanup --apply: Requires explicit --apply flag for worktree removal


## v0.2.3 - Jujutsu (jj) Support ✅

---

---


### Goal
Formalize a critical architectural boundary: Village must not depend directly on Git semantics. Enable painless Jujutsu (jj) support without core logic refactoring.

### Scope

- [x] **SCM Interface Protocol**
  \`\`\`python
  class SCM(Protocol):
      kind: Literal["git", "jj"]

      def ensure_repo(repo_root: Path) -> None
      def check_clean(repo_root: Path) -> bool
      def ensure_workspace(repo_root: Path, workspace_path: Path, base_ref: str = "HEAD") -> None
      def remove_workspace(workspace_path: Path) -> bool
      def list_workspaces(repo_root: Path) -> list[WorkspaceInfo]
  \`\`\`

- [x] **Git Backend Implementation**
  - \`village/scm/git.py\`: GitSCM implements SCM Protocol
  - All Git commands isolated within GitSCM class
  - Maintains 100% backward compatibility
  - Uses Git porcelain format (\`git worktree list --porcelain\`)

- [x] **Workspace Model Refactoring**
  - Directory name encodes task ID (\`.worktrees/bd-a3f8/\`)
  - Directory is authoritative identity
  - SCM metadata irrelevant to Village core
  - \`resolve_task_id()\` extracts task ID from workspace path (Village-specific)

- [x] **Configuration Updates**
  \`\`\`ini
  [DEFAULT]
  SCM=git
  WORKTREES_DIR=.worktrees
  SESSION=village
  \`\`\`

  Environment variable: \`VILLAGE_SCM=git|jj\`

- [x] **Testing**
  - Unit tests for SCM Protocol interface
  - Unit tests for GitSCM backend
  - Integration tests verify backward compatibility
  - 294 tests passing (16 worktrees + 278 others)
  - Coverage: 64% overall, 100% for scm modules

### Success Criteria
- [x] Zero git commands outside \`village/scm/git.py\`
- [x] Core logic is SCM-agnostic
- [x] jj backend possible without core refactor
- [x] Codebase maintained (294 tests passing, full backward compatibility)

### Migration Notes
- No user-visible changes expected
- Existing worktrees and lock files remain compatible
- Git backend behavior is preserved
- All existing Village commands work identically

---


### Goal
Strengthen operational trust under heavy concurrency and frequent crashes. Make Village feel reliable even in production use.

### Scope

- [x] **Event Log (NDJSON)**
  - Append-only log at \`.village/events.log\`
  - Each action appends one JSON line:
    \`\`\`json
    {"ts":"2026-01-22T10:41:12","cmd":"queue","task":"bd-a3f8","pane":"%12","result":"ok"}
    \`\`\`
  - No indexing, no database, no rotation required
  - Uses: crash recovery inspection, deduplication, debugging

- [x] **Queue Deduplication Guard**
  - Consult \`events.log\` before starting tasks
  - Skip tasks started within configurable TTL (default: 5 minutes)
  - Override via \`village queue --force\`
  - Config: \`QUEUE_TTL_MINUTES\` or \`VILLAGE_QUEUE_TTL_MINUTES\` env var

- [x] **Expanded \`--plan\` Output**
  - \`queue --plan --json\` returns:
    - Tasks selected
    - Tasks skipped (with reason per task)
    - Locks involved (pane_id, window, agent, claimed_at)
    - Workspace paths
  - Enables dry-run scheduling validation

- [x] **Cleanup Enhancements**
  - \`village cleanup --apply\` removes orphan and stale worktrees
  - Safer corrupted lock handling via \`parse_lock_safe()\`
  - Separate orphan_worktrees and stale_worktrees in CleanupPlan

- [x] **Testing & Integration**
  - 58 new SCM tests (protocol compliance + Git backend + JJ placeholders)
  - 3 v1.2 integration tests (event logging, deduplication, cleanup)
  - Coverage: 74% overall (git.py: 85%, protocol: 100%)

### Success Criteria

- [x] Users can trust \`queue\` under concurrency
- [x] Failures are explainable post-mortem
- [x] Shell scripts can reason via exit codes
- [x] No task accidentally runs twice

### Technical Notes

- Event log: village/event_log.py (78 lines)
- Deduplication: village/queue.py + village/config.py (TTL config)
- Cleanup: village/cleanup.py with --apply flag
- Tests: tests/test_event_log.py, tests/test_queue.py, tests/test_cleanup.py, tests/scm/test_*.py
- Coverage: 74% (2936 statements, 777 missed)
- Timezone handling: Fixed to use datetime.now(timezone.utc)

### Migration Notes

No migration required. All features backward compatible.

- Event logging: Automatic, no user action needed
- Queue deduplication: Opt-in via --force flag
- Cleanup --apply: Requires explicit --apply flag for worktree removal

---


### Goal
Add Jujutsu (jj) as a second SCM backend, validating v1.1 SCM abstraction design. Provide early value for jj users without waiting for v2's more complex features.

### Scope

- [x] **JJSCM Backend Implementation**
  - New file: `village/scm/jj.py` implements SCM Protocol
  - Map jj commands to SCM protocol methods:
    - `ensure_repo()` → `jj git init`
    - `check_clean()` → `jj status` (no working copy changes)
    - `ensure_workspace()` → `jj workspace add`
    - `remove_workspace()` → `jj workspace forget`
    - `list_workspaces()` → `jj workspace list`
  - Handle jj-specific error handling (jj binary not found, repo not found)

- [x] **Workspace Naming Convention**
  - Keep Village's `.worktrees/bd-a3f8/` pattern (task ID in directory name)
  - Directory = authoritative identity (Village-specific, not SCM-specific)
  - JJ workspace names use default basename (equals task ID since directory is named by task ID)
  - `resolve_task_id()` extracts task ID from workspace path (works for both git and jj)

- [x] **Configuration Integration**
  - Add `SCM=jj` opt-in via environment variable or config file
  - Environment variable: `VILLAGE_SCM=jj`
  - Config file support:
    ```ini
    [DEFAULT]
    SCM=jj
    ```
  - Default remains `SCM=git` (git is established, jj is experimental)

- [x] **Error Handling**
  - Fail fast if `jj` binary not found with clear error message
  - Validate jj repository exists before operations
  - Handle jj workspace conflicts gracefully

- [x] **Testing Strategy**
  - New file: `tests/scm/test_jj_backend.py`
  - Hybrid approach: reusable fixtures + real jj repos (not mocked)
  - Test fixtures in `tests/fixtures/jj_repos/` for common scenarios
  - Unit tests for all SCM protocol methods
  - Integration tests verifying Village commands work with jj backend
  - Target test coverage: >80% for jj_backend
  - Validate protocol compliance (same tests as GitSCM)

- [x] **Documentation**
  - Update README.md with jj support notes
  - Add example config showing `SCM=jj`
  - Document no migration required for git users
  - Explain workspace naming strategy

### Design Decisions

1. **Workspace naming**: Use default basename (equals task ID)
   - Village names directory `.worktrees/bd-a3f8/`
   - JJ workspace name = basename of destination = task ID
   - No `--name` flag needed (unnatural for our use case)
   - Ensures basename always equals task ID (guaranteed by Village)

2. **Config approach**: Keep git as default, jj as opt-in
   - Rationale: Git is established, jj is in growth phase
   - No breaking changes for existing git users
   - Validates jj's experimental status

3. **Testing approach**: Reusable fixtures with real jj repos
   - Not mocked (brittle) but not E2E (slow)
   - `tests/fixtures/jj_repos/` for common scenarios
   - Balance realism and test speed

4. **Error handling**: Fail fast if jj not installed
   - Clear error message: "jj binary not found in PATH"
   - No fallback to git (confusing for user intent)
   - User must install jj or switch to `SCM=git`

### Files to Create/Modify

**New files:**
- `village/scm/jj.py` (150-200 lines)
- `tests/scm/test_jj_backend.py` (200-300 lines)
- `tests/fixtures/jj_repos/` (reusable jj repo fixtures)

**Modified files:**
- `village/config.py` (add jj config support)
- `README.md` (update with jj support notes)
- `AGENTS.md` (maybe add jj-specific testing guidance)

### Success Criteria

- [x] JJ backend passes all SCM protocol compliance tests
- [x] Village commands work identically with `SCM=jj` vs `SCM=git`
- [x] Zero git commands outside `village/scm/git.py`
- [x] Zero jj commands outside `village/scm/jj.py`
- [x] Test coverage >80% for jj_backend
- [x] Documentation updated (README, config examples)
- [x] Backward compatibility verified (git users unaffected)
- [x] Error handling validated (jj not installed, invalid repos)

### Migration Notes

**For existing git users:**
- No migration required
- Git backend remains default
- All existing functionality preserved

**For new jj users:**
- Set `SCM=jj` in `.village/config` or environment variable
- Must have `jj` CLI installed and in PATH
- Village workspaces use `.worktrees/bd-a3f8/` pattern (independent of jj workspace names)

### Timeline Estimate

- **Total time**: 8-12 hours (spread over 2-3 days)
- **Phase breakdown**:
  - Design & API definition: 1-2 hrs
  - JJSCM implementation: 2-3 hrs
  - Config integration: 0.5 hrs
  - Testing: 2-3 hrs
  - Documentation: 1-2 hrs
  - Validation: 1 hr

### Technical Notes

- JJ workspace commands: `jj workspace add <dest>`, `jj workspace forget`, `jj workspace list`
- JJ uses Git backend by default: `jj git init`, `jj git clone`, `jj git export/import`
- Workspace directory = authoritative identity (Village-specific convention)
- JJ workspace names are internal to jj (shown in `jj log` as `<name>@`)
- `resolve_task_id()` logic unchanged (extracts from path, not SCM metadata)

---

## v0.3.0 - Safety & Coordination (Essential)

### Goal
Strengthen Village's core value as coordination layer - features OpenCode cannot provide.

### Scope

- [x] **State Machine Workflows**
  - **Task lifecycle states**: QUEUED → CLAIMED → IN_PROGRESS → PAUSED → COMPLETED → FAILED
  - **State transitions**: Validate and log all transitions
  - **New file**: `village/state_machine.py` (~200 lines)
  - **Commands**:
    ```bash
    village pause bd-a3f8         # Pause in-progress task
    village resume-task bd-a3f8   # Resume paused task
    village state bd-a3f8          # Show task state history
    ```

- [x] **Automatic Rollback on Failure**
  - **Worktree reset**: If task fails, revert worktree to clean state
  - **Lock update**: Mark task as FAILED in lock file
  - **Event logging**: Log rollback events to events.log
  - **Configuration**: `ROLLBACK_ON_FAILURE=true|false` (default: true)
  - **Integration**: Modify `resume.py` to wrap OpenCode execution in try/except

- [x] **Conflict Detection**
  - **File overlap detection**: Detect when agents modify same files
    ```python
    def detect_file_conflicts(active_workers):
        modified_files = []
        for worker in active_workers:
            files = get_modified_files_in_worktree(worker.worktree_path)
            modified_files.extend(files)
        return find_overlaps(modified_files)
    ```
  - **Integration**: Check conflicts in `arbitrate_locks()` before claiming
  - **Warning**: `village queue --conflicts` shows potential conflicts
  - **Block on conflict**: Configurable `BLOCK_ON_CONFLICT=true|false`

### Design Decisions

1. **State machine as core coordination primitive**
   - Enables tracking task lifecycle
   - Validates state transitions (prevents invalid operations)
   - Supports pause/resume workflows

2. **Automatic rollback on failure**
   - Ensures clean recovery from errors
   - Prevents partial state corruption
   - User-controllable via config

3. **Conflict detection prevents data corruption**
   - Detects when agents modify same files
   - Blocks task execution if conflict detected
   - Configurable blocking (warn-only vs block)

### Files to Create/Modify

**New files:**
- `village/state_machine.py` (~200 lines)
- `village/conflict_detection.py` (~150 lines)

**Modified files:**
- `village/queue.py` (integrate conflict detection)
- `village/resume.py` (add rollback logic)
- `village/config.py` (add new config options)

**Test files to create:**
- `tests/test_state_machine.py`
- `tests/test_conflicts.py`

### Success Criteria

- [x] State machine transitions are validated and logged
- [x] Automatic rollback recovers from failed tasks
- [x] File conflicts detected before task execution
- [x] Test coverage >85% for new modules
- [x] Documentation updated (README, examples)

### Timeline Estimate

- **Total time**: 16-20 hours (spread over 2-3 weeks)
- **Phase breakdown**:
  - State machine design & implementation: 4-5 hrs
  - Rollback design & implementation: 3-4 hrs
  - Conflict detection design & implementation: 3-4 hrs
  - Config integration: 1 hr
  - Testing: 3-4 hrs
  - Documentation: 1-2 hrs

### Technical Notes

- State machine: Validate transitions, log all state changes to events.log
- Rollback: Use SCM commands to reset worktree (git reset, jj abandon)
- Conflict detection: Parse git/jj status, compare file sets across workers
- Event logging: All state changes and rollback attempts logged

---


### Goal
Provide system-wide visibility that OpenCode cannot offer.

### Scope

- [ ] **Real-Time Dashboard**
  - **New command**: `village dashboard --watch`
  - **Live display** (refresh every 2s):
    ```
    ┌─────────────────────────────────────────────────────────────┐
    │ Village Dashboard (Refresh: 2s)                          │
    ├─────────────────────────────────────────────────────────────┤
    │ Active Workers (2/4)                                    │
    │ TASK_ID    STATUS    AGENT      PANE     WINDOW          │
    │ bd-a3f8    ACTIVE    build      %12      build-1-bd-a3f8│
    │ bd-b7c2    ACTIVE    frontend   %13      frontend-1-bd-b7c2│
    │                                                             │
    │ Task Queue (3 ready, 2 blocked)                            │
    │ bd-c9d1 [READY]    high-priority                       │
    │ bd-e4f2 [READY]    feature                             │
    │ bd-f5g3 [READY]    fix                                 │
    │                                                             │
    │ Lock Status: 2 ACTIVE, 1 STALE, 0 orphans                │
    │ System Load: 2.3 / 8.0 (max workers: 4)               │
    └─────────────────────────────────────────────────────────────┘
    ```
  - **Terminal UI**: Use `rich.console` or similar
  - **Interactive**: Press 'q' to quit, 'r' to refresh

- [ ] **Metrics Export**
  - **Backends**: Prometheus, StatsD, Custom
  - **New command**: `village metrics export --backend prometheus`
  - **Metrics exposed**:
    - `village_active_workers` (gauge)
    - `village_queue_length` (gauge)
    - `village_stale_locks` (gauge)
    - `village_orphans_count` (gauge)
    - `village_task_completion_rate` (histogram)
    - `village_average_task_duration_seconds` (histogram)
  - **New file**: `village/metrics.py` (~200 lines)
  - **Configuration**:
    ```ini
    [metrics]
    backend=prometheus
    port=9090
    export_interval_seconds=60
    ```

- [ ] **Structured Event Queries**
  - **New command**: `village events --task bd-a3f8 --last 1h --json`
  - **Filters**: `--task <id>`, `--status <STATUS>`, `--since <datetime>`, `--last <duration>`
  - **Output**: JSON or table format
  - **Integration**: Query `.village/events.log` with filtering
  - **New file**: `village/event_query.py` (~150 lines)

### Design Decisions

1. **Real-time dashboard for production monitoring**
   - Live visibility into system state
   - Refresh interval configurable (default: 2s)
   - Minimal dependencies (rich.console or similar)

2. **Metrics export integrates with existing monitoring stacks**
   - Prometheus and StatsD support for production environments
   - Custom backend option for other systems
   - Export interval configurable (default: 60s)

3. **Event queries enable historical analysis**
   - Filter by task, status, time range
   - JSON output for tooling integration
   - Table output for human readability

### Files to Create/Modify

**New files:**
- `village/dashboard.py` (~300 lines)
- `village/metrics.py` (~200 lines)
- `village/event_query.py` (~150 lines)

**Modified files:**
- `village/config.py` (add metrics/dashbard config)
- `village/cli.py` (add new commands)

**Test files to create:**
- `tests/test_dashboard.py`
- `tests/test_metrics.py`
- `tests/test_event_query.py`

### Success Criteria

- [ ] Real-time dashboard displays live system state
- [ ] Metrics export works for Prometheus and StatsD
- [ ] Event queries filter and format correctly
- [ ] Test coverage >80% for new modules
- [ ] Documentation updated

### Timeline Estimate

- **Total time**: 12-16 hours (spread over 1-2 weeks)
- **Phase breakdown**:
  - Dashboard design & implementation: 4-5 hrs
  - Metrics design & implementation: 3-4 hrs
  - Event queries design & implementation: 2-3 hrs
  - Config integration: 1 hr
  - Testing: 2-3 hrs
  - Documentation: 1-2 hrs

### Technical Notes

- Dashboard: Use rich.console or similar terminal UI library
- Metrics: HTTP server for Prometheus scrape endpoint, UDP socket for StatsD
- Event queries: Parse NDJSON events.log, apply filters, output formatted results

---

## v1.0.0 - Production-Ready Coordination (Essential)

### Goal
Village is indispensable coordination infrastructure with audit trails, safety guarantees, and production reliability.

### Scope

- [ ] **Audit Trails Emphasis**
  - Add "Audit & Trust" section to README and PRD
  - Emphasize local, auditable source code advantage
  - Document all audit features (event logs, stack traces, deterministic behavior)
  - Contrast with LLM black boxes

- [ ] **Test Coverage >85%**
  - Ensure overall coverage >85%
  - Ensure critical modules >90% (queue, resume, locks, state_machine)
  - Add missing tests for edge cases

- [ ] **Zero Critical Bugs**
  - No exit code 1 crashes in production
  - All error paths tested and documented
  - Graceful degradation on errors

- [ ] **Complete Documentation**
  - README comprehensive with all commands
  - PRD complete with success criteria
  - Examples cover common workflows
  - Troubleshooting guide comprehensive
  - CHANGELOG.md comprehensive

- [ ] **CHANGELOG.md Comprehensive**
  - Document all version changes
  - Organized by version with dates
  - Includes breaking changes, features, fixes, tests

### Design Decisions

1. **Audit trails as production requirement**
   - All operations logged with stack traces
   - Source code version in log entries
   - Deterministic behavior (same inputs → same outputs)

2. **Production readiness checklist**
   - Not just code quality, but operational readiness
   - Documentation, testing, monitoring all complete
   - Migration guides provided when needed

### Files to Modify

**Modified files:**
- `docs/PRD.md` (add "Village vs OpenCode+PPC" and "Audit & Trust" sections)
- `README.md` (add "Local, Auditable" emphasis)
- `docs/CHANGELOG.md` (ensure comprehensive)
- All source files (add missing tests)

### Success Criteria (v1.0.0 Release Checklist)

**Critical Differentiators (v0.3.0):**
- [ ] State machine workflows working
- [ ] Automatic rollback functional
- [ ] Conflict detection operational

**Observability (v0.4.0):**
- [ ] Real-time dashboard functional
- [ ] Metrics export working
- [ ] Event queries operational

**Production Readiness:**
- [ ] Test coverage >85% overall
- [ ] Zero critical bugs in production
- [ ] Documentation complete (README, PRD, examples, troubleshooting)
- [ ] CHANGELOG.md up-to-date
- [ ] Audit trails comprehensive

### Timeline Estimate

- **Total time**: 24-28 hours (spread over 3-4 weeks)
- **Phase breakdown**:
  - Audit trail documentation: 2-3 hrs
  - Test coverage improvement: 6-8 hrs
  - Bug fixes and stabilization: 8-10 hrs
  - Documentation completion: 4-5 hrs
  - Validation and testing: 2-2 hrs

### Technical Notes

- Coverage: Use pytest-cov, aim for >85% across all modules
- Audit trails: Ensure all critical paths log to events.log with context
- Documentation: Ensure all commands documented with examples

---

## v1.1.0 - High-ROI Integrations (Tier 1)

### Goal
Automate high-value workflows that save significant time and improve team productivity.

### Scope

- [ ] **E2E Test Suite**
  - **Comprehensive end-to-end testing**: 30+ tests
  - **New file**: `tests/test_e2e.py` (600-800 lines)
  - **Test classes**:
    - `TestOnboardingE2E`: New project workflow
    - `TestMultiTaskExecutionE2E`: Queue multiple tasks
    - `TestCrashRecoveryE2E`: Crash and cleanup
    - `TestConcurrencyE2E`: Parallel queue execution
    - `TestFullUserJourneyE2E`: Complete lifecycle
  - **Coverage**: Onboarding, multi-task, crash recovery, concurrency, full journey

- [ ] **GitHub Integration**
  - **PR Description Generator**:
    ```bash
    village pr describe bd-a3f8
    ```
  - Extracts task metadata from Beads
  - Analyzes git diff in worktree
  - Generates PR description with:
    - Summary (from task title/description)
    - Changes (git diff summary)
    - Testing checklist (from task success criteria)
    - Related tasks (from Beads dependencies)
  - Opens PR or outputs to stdout
  - **PR Status Sync**:
    ```bash
    village pr sync --from-beads
    ```
  - Updates PR status based on Beads task status
  - Adds labels: `in-progress`, `completed`, `blocked`
  - **New file**: `village/github_integration.py` (~250 lines)

- [ ] **CI/CD Hooks**
  - **Build Triggers**:
    ```bash
    village ci trigger --task bd-a3f8
    ```
  - Triggers CI/CD build for completed task
  - Monitors build status
  - Updates task status on failure
  - **Configuration**:
    ```ini
    [ci.github_actions]
    enabled=true
    trigger_on_task_complete=true
    notify_on_failure=true
    ```
  - **Integration**: Hook into `resume.py` completion events
  - **New file**: `village/ci_integration.py` (~200 lines)

- [ ] **Notification Systems**
  - **Webhook Support**:
    - Slack, Discord, Email, Custom
  - Triggered on events: task_failed, orphan_detected, high_priority_task
  - **Configuration**:
    ```ini
    [notifications.slack]
    enabled=true
    webhook_url=https://hooks.slack.com/services/...
    events=task_failed,orphan_detected

    [notifications.email]
    enabled=false
    address=team@example.com
    events=task_failed
    ```
  - **Integration**: Hook into event logging
  - **New file**: `village/notifications.py` (~180 lines)

### Design Decisions

1. **E2E tests as high-ROI investment**
   - Ensures production reliability
   - Prevents regressions
   - Validates complete workflows

2. **GitHub integration accelerates PR workflows**
   - Automates PR description generation
   - Syncs PR status with task completion
   - Reduces manual work significantly

3. **CI/CD hooks catch regressions early**
   - Automatic build triggers
   - Status updates on failure
   - Prevents merging broken code

4. **Notification systems improve incident response**
   - Immediate awareness of failures
   - Configurable event filters
   - Multiple notification backends

### Files to Create/Modify

**New files:**
- `tests/test_e2e.py` (600-800 lines, comprehensive E2E)
- `village/github_integration.py` (~250 lines)
- `village/ci_integration.py` (~200 lines)
- `village/notifications.py` (~180 lines)

**Modified files:**
- `village/config.py` (add CI/notification config)
- `village/resume.py` (hook CI triggers)
- `village/event_log.py` (hook notification events)

**Test files to create:**
- Tests for github_integration.py
- Tests for ci_integration.py
- Tests for notifications.py

### Success Criteria

- [ ] E2E test suite passes (>30 tests)
- [ ] GitHub PR automation works correctly
- [ ] PR status syncs with Beads
- [ ] CI/CD triggers execute on task completion
- [ ] Notifications sent for configured events
- [ ] Test coverage >75% for integration modules

### Timeline Estimate

- **Total time**: 32-40 hours (spread over 3-4 weeks)
- **Phase breakdown**:
  - E2E test suite: 10-12 hrs
  - GitHub integration: 6-8 hrs
  - CI/CD hooks: 4-5 hrs
  - Notification systems: 4-5 hrs
  - Config integration: 2-3 hrs
  - Testing: 4-5 hrs
  - Documentation: 1-2 hrs

### Technical Notes

- E2E tests: Use real Beads, tmux, git/jj where possible
- GitHub integration: GitHub CLI, git diff parsing, Beads task data extraction
- CI/CD: GitHub Actions API, GitLab CI, Jenkins integration
- Notifications: Webhook POST requests, JSON payloads, retry logic

---

## v1.2.0 - Medium-ROI Optimizations (Tier 2)

### Goal
Optimize throughput and user experience with medium-ROI features.

### Scope

- [ ] **Advanced Scheduling Policies**
  - **Priority-based scheduling**: High-impact tasks first
  - **Resource-aware scheduling**: Respect CPU/memory limits
  - **Fair-share scheduling**: Balance agent allocation
  - **Dependency-aware scheduling**: Optimize task order based on Beads DAG
  - **Priority-based task stealing**: High-priority tasks steal STALE locks after shorter timeout
  - **Configuration**: `village queue --priority high` to enable priority scheduling
  - **Integration**: Extend `arbitrate_locks()` in queue.py
  - **New file**: `village/scheduler.py` (~250 lines)

- [ ] **PR Description Generator**
  - **Automated PR descriptions**:
    ```bash
    village pr describe bd-a3f8
    ```
  - Extracts task metadata from Beads
  - Analyzes git diff in worktree
  - Generates PR description with:
    - Summary (from task title/description)
    - Changes (git diff summary)
    - Testing checklist (from task success criteria)
    - Related tasks (from Beads dependencies)
  - **New file**: `village/pr_generator.py` (~150 lines)

- [ ] **Multi-Repo Coordination**
  - **Configuration**:
    ```ini
    [repo.backend]
    path=../backend
    agent=backend-build

    [repo.frontend]
    path=../frontend
    agent=frontend-build
    ```
  - **Commands**:
    ```bash
    village queue --repo backend --n 3
    village queue --repo frontend --n 2
    village status --repos
    ```
  - **Integration**: Cross-repo task routing, worktree isolation per repo
  - **Modify**: `village/queue.py` (multi-repo support)

### Design Decisions

1. **Advanced scheduling optimizes throughput**
   - Priority scheduling for critical tasks
   - Resource-aware to prevent overload
   - Fair-share for agent balancing
   - DAG-aware for optimal ordering

2. **PR description generator improves review process**
   - Consistent PR format
   - Automatic testing checklists
   - Links to related tasks
   - Reduces manual documentation work

3. **Multi-repo coordination for microservices**
   - Config per repo
   - Shared lock state across repos
   - Cross-repo task routing
   - Worktree isolation maintained

### Files to Create/Modify

**New files:**
- `village/scheduler.py` (~250 lines)
- `village/pr_generator.py` (~150 lines)

**Modified files:**
- `village/queue.py` (integrate scheduling, multi-repo)
- `village/config.py` (add repo config)

**Test files to create:**
- `tests/test_scheduler.py`
- `tests/test_pr_generator.py`
- Tests for multi-repo features

### Success Criteria

- [ ] Priority scheduling works correctly
- [ ] Resource-aware scheduling respects system limits
- [ ] Fair-share scheduling balances agent load
- [ ] PR descriptions generated automatically
- [ ] Multi-repo tasks route correctly
- [ ] Test coverage >80% for new modules

### Timeline Estimate

- **Total time**: 24-28 hours (spread over 3-4 weeks)
- **Phase breakdown**:
  - Advanced scheduling: 6-8 hrs
  - PR generator: 3-4 hrs
  - Multi-repo: 6-8 hrs
  - Config integration: 2-3 hrs
  - Testing: 4-5 hrs
  - Documentation: 1-2 hrs

### Technical Notes

- Scheduling: Extend existing queue.py with policy functions
- PR generator: Beads task extraction, git diff parsing, markdown generation
- Multi-repo: Config parser, worktree path resolution, lock state isolation

---

## v1.3.0 - Low-ROI Features (Tier 3)

### Goal
Add nice-to-have features for specific use cases with low priority.

### Scope

- [ ] **Resource Quotas**
  - **Resource limits per agent**:
    ```ini
    [resources]
    max_cpu=4.0
    max_memory_gb=16
    max_disk_gb=50

    [agent.build]
    quota_cpu=2.0
    quota_memory_gb=8
    ```
  - **Pre-flight checks**: Verify quotas before claiming task
  - **Integration**: Extend `arbitrate_locks()` in queue.py
  - **New file**: `village/resource_quotas.py` (~180 lines)

- [ ] **Dynamic DAG Re-evaluation**
  - **Runtime dependency resolution**:
    ```python
    def generate_queue_plan(session_name, max_workers):
        tasks = get_beads_ready()
        # Re-evaluate dependencies (Beads might be stale)
        for task in tasks:
            dependencies = get_beads_dependencies(task.id)
            if not all_dependencies_satisfied(dependencies):
                tasks.remove(task)
        return tasks
    ```
  - **Task Status Sync**:
    ```bash
    village sync --to-beads
    ```
  - Syncs Village lock status back to Beads
  - Updates task statuses: CLAIMED, IN_PROGRESS, FAILED
  - **New file**: `village/dag_reeval.py` (~200 lines)

### Design Decisions

1. **Resource quotas prevent exhaustion**
   - Enforce CPU/memory/disk limits
   - Pre-flight checks before task execution
   - Configurable per agent

2. **Dynamic DAG re-evaluation ensures correctness**
   - Re-calculate readiness at queue time
   - Detect stale Beads DAG state
   - Sync status back to Beads

### Files to Create/Modify

**New files:**
- `village/resource_quotas.py` (~180 lines)
- `village/dag_reeval.py` (~200 lines)

**Modified files:**
- `village/queue.py` (integrate quotas, DAG re-eval)
- `village/config.py` (add quota config)

**Test files to create:**
- `tests/test_resource_quotas.py`
- `tests/test_dag_reeval.py`

### Success Criteria

- [ ] Resource quotas enforced
- [ ] DAG re-evaluation works correctly
- [ ] Task status syncs with Beads
- [ ] Test coverage >80% for new modules

### Timeline Estimate

- **Total time**: 20-24 hours (spread over 3-4 weeks)
- **Phase breakdown**:
  - Resource quotas: 4-5 hrs
  - DAG re-evaluation: 5-6 hrs
  - Config integration: 2-3 hrs
  - Testing: 4-5 hrs
  - Documentation: 1-2 hrs
  - Validation: 1 hr

### Technical Notes

- Resource quotas: System load monitoring (psutil or similar), pre-flight checks
- DAG re-evaluation: Beads DAG API, dependency graph traversal, runtime validation

---

## Definition of Done

Village should feel like:

> "a tiny operating system for parallel development."

Nothing hidden. Everything inspectable. Flow first.

---

## Implementation Timeline

| Version | Type | Status | Time Estimate |
|---------|-------|--------|----------------|
| v0.2.3 | Release | ✅ Complete | 8-12 hrs |
| v0.3.0 | Essential | 📅 Planned | 16-20 hrs |
| v0.4.0 | Essential | 📅 Planned | 12-16 hrs |
| v1.0.0 | Production | 📅 Planned | 24-28 hrs |
| v1.1.0 | High-ROI | 📅 Planned | 32-40 hrs |
| v1.2.0 | Medium-ROI | 📅 Planned | 24-28 hrs |
| v1.3.0 | Low-ROI | 📅 Planned | 20-24 hrs |

---

## Optional Extensions (Future)

See [docs/PROPOSALS.md](PROPOSALS.md) for optional feature ideas, including:

- **Fabric Integrations** (ROI-sorted tiers)
  - Tier 1: `village chat`, agent contract generation
  - Tier 2: Task drafting (human-approved), project summaries
  - Tier 3: PR description generator, release notes

- **Enhanced Observability** (ROI-sorted tiers)
  - Real-time dashboards
  - Metrics export (Prometheus, StatsD)
  - Performance profiling

- **Advanced Workflows** (ROI-sorted tiers)
  - Multi-repo support
  - Remote tmux sessions
  - Custom scheduler policies

---

## Contributing

See [AGENTS.md](../AGENTS.md) for development guidelines.

When implementing features from this roadmap:

1. Create a feature branch from main
2. Reference roadmap item in commit messages
3. Update this ROADMAP.md as you complete items
4. Ensure tests pass and coverage is maintained
5. Run linting: `uv run ruff check . && uv run mypy village/`
