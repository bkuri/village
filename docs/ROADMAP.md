# Village Roadmap

## Current Status: v0.1.0-alpha

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
  - [ ] Migration notes from bash version

- [x] **Phase 12**: Chat interface
  - [x] Knowledge-share mode
  - [x] Task-create mode with drafts
  - [x] Context file management
  - [x] Read-only subcommands
  - [x] Session state persistence

### Current Statistics

- **Total Python LOC**: ~4,000 (exceeds 2k target due to chat feature)
- **Test Coverage**: >85% core commands, >90% resume flow
- **Commands Implemented**: 11 (up, down, status, ready, resume, queue, cleanup, unlock, locks, drafts, chat)

---

## v1.1 - SCM-Abstraction Edition ✅

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

---

## v1.2 - Reliability & Observability

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

### Success Criteria

- [ ] Users can trust `queue` under concurrency
- [ ] Failures are explainable post-mortem
- [ ] Shell scripts can reason via exit codes
- [ ] No task accidentally runs twice

### Technical Notes

- Event log is simple append-only (no write conflicts)
- TTL-based deduplication is heuristic (not perfect, but safe)
- JSON output remains versioned and stable

---

## v1.3 - Jujutsu (jj) Support

### Goal
Add Jujutsu (jj) as a second SCM backend, validating the v1.1 SCM abstraction design. Provide early value for jj users without waiting for v2's more complex features.

### Scope

- [ ] **JJSCM Backend Implementation**
  - New file: `village/scm/jj.py` implements SCM Protocol
  - Map jj commands to SCM protocol methods:
    - `ensure_repo()` → `jj git init`
    - `check_clean()` → `jj status` (no working copy changes)
    - `ensure_workspace()` → `jj workspace add`
    - `remove_workspace()` → `jj workspace forget`
    - `list_workspaces()` → `jj workspace list`
  - Handle jj-specific error handling (jj binary not found, repo not found)

- [ ] **Workspace Naming Convention**
  - Keep Village's `.worktrees/bd-a3f8/` pattern (task ID in directory name)
  - Directory = authoritative identity (Village-specific, not SCM-specific)
  - JJ workspace names use default basename (equals task ID since directory is named by task ID)
  - `resolve_task_id()` extracts task ID from workspace path (works for both git and jj)

- [ ] **Configuration Integration**
  - Add `SCM=jj` opt-in via environment variable or config file
  - Environment variable: `VILLAGE_SCM=jj`
  - Config file support:
    ```ini
    [DEFAULT]
    SCM=jj
    ```
  - Default remains `SCM=git` (git is established, jj is experimental)

- [ ] **Error Handling**
  - Fail fast if `jj` binary not found with clear error message
  - Validate jj repository exists before operations
  - Handle jj workspace conflicts gracefully

- [ ] **Testing Strategy**
  - New file: `tests/scm/test_jj_backend.py`
  - Hybrid approach: reusable fixtures + real jj repos (not mocked)
  - Test fixtures in `tests/fixtures/jj_repos/` for common scenarios
  - Unit tests for all SCM protocol methods
  - Integration tests verifying Village commands work with jj backend
  - Target test coverage: >80% for jj_backend
  - Validate protocol compliance (same tests as GitSCM)

- [ ] **Documentation**
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

## v2 - Workspace-Native Parallelism

### Goal
Expand framework without compromising core principles. Focus on workspace-native execution and long-running resilience.

### Scope

- [ ] **Reconciliation Engine**
   - New command: `village reconcile [--plan|--apply]`
   - Detects and repairs inconsistencies:
     - Tmux panes vs lock files
     - Lock files vs workspaces
     - Workspaces vs Beads tasks
   - Outputs planned actions before execution

- [ ] **Resource-Aware Queueing** (Optional)
   - Scheduling constraints:
     - `--max-workers` (already implemented)
     - `--max-load` (new: system load average)
     - `--max-mem` (new: available memory)
   - Implemented as pre-flight checks only
   - Village does not manage resources — it respects them

- [ ] **Hooks System**
   - Optional executable hooks in `.village/hooks/`:
     - `on-claim`: Invoked when task is claimed
     - `on-release`: Invoked when task is released
     - `on-fail`: Invoked when task fails
   - Invoked with structured JSON payloads
   - Enables: notifications, custom logging, PR automation, metrics export

- [ ] **Contract Caching**
   - Deterministic prompt contracts cached at:
     ```
     .village/contracts/<task>/<agent>.md
     ```
   - Prevents unnecessary LLM regeneration
   - Cache invalidation strategy TBD

### Explicit Non-Goals

- Daemon mode
- Distributed workers
- Central coordination server
- YAML workflows
- Plugin marketplaces

### Philosophy Reminder

Village v2 adds power — not magic. It remains:
- Local-first
- File-based
- tmux-truth-driven
- Human-debuggable

---

## Optional Extensions (Future)

See [docs/PROPOSALS.md](PROPOSALS.md) for optional feature ideas, including:

- **Fabric Integrations** (ROI-sorted tiers)
  - Tier 1: `village chat`, agent contract generation
  - Tier 2: Task drafting (human-approved), project summaries
  - Tier 3: PR description generator, release notes

- **Enhanced Observability**
  - Metrics export (Prometheus, StatsD)
  - Real-time dashboards
  - Performance profiling

- **Advanced Workflows**
  - Multi-repo support
  - Remote tmux sessions
  - Custom scheduler policies

- **End-to-End Testing** (NEW)
  - Installation testing (pip install, verify CLI commands)
  - Onboarding tests (village init, config setup)
  - Day-to-day workflow tests (queue, resume, status, cleanup)
  - Multi-task execution tests (concurrency, deduplication)
  - Crash recovery tests (event log inspection)
  - Full user journey tests (new project → complete workflow)

---

## Definition of Done

Village should feel like:

> "a tiny operating system for parallel development."

Nothing hidden. Everything inspectable. Flow first.

---

## Implementation Timeline

| Version | Target | Status |
|---------|--------|--------|
| v0.1.0 | Alpha | ✅ Released |
| v1.0 | Stable beta | 🔄 In progress |
| v1.1 | SCM abstraction | ✅ Complete |
| v1.2 | Reliability | ✅ Complete |
| v1.3 | Jujutsu (jj) support | ✅ Complete |
| v2.0 | Workspace-native | 📅 Future |

---

## Contributing

See [AGENTS.md](../AGENTS.md) for development guidelines.

When implementing features from this roadmap:

1. Create a feature branch from main
2. Reference the roadmap item in commit messages
3. Update this ROADMAP.md as you complete items
4. Ensure tests pass and coverage is maintained
5. Run linting: `uv run ruff check . && uv run mypy village/`
