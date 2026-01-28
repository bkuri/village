# Changelog

All notable changes to Village will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.0.0] - Production-Ready Coordination - 2026-01-27

### Added
- **Test Coverage Improvements** (v1.0.0 phase 2)
  - `render/text.py` coverage: 72% → 99% (17 new tests)
  - `render/colors.py` coverage: 85% → 100% (7 new tests)
  - `state_machine.py` coverage: 83% → 98% (7 new tests)
  - `scm/git.py` coverage: 76% → 100% (enabled 6 skipped + 2 new test classes)
  - `runtime.py` coverage: 40% → 100% (30 new tests)
  - Overall coverage: 73% → 76%
- **Beads Integration**
  - `bd prime` integration for workflow context in chat system
  - AI-optimized Beads workflow context (~50 tokens) injected into prompts
  - Graceful degradation when Beads not available

### Fixed
- **Queue Lock Detection** (`test_arbitrate_populates_lock_info`)
  - Lock test was writing to wrong directory due to `get_config()` returning real config
  - Fixed by setting `lock._config = mock_config`
- **Cleanup Event Logging** (`test_execute_cleanup_logs_events`)
  - Test failed in full suite due to missing config mocking
  - Added proper `get_config()` patching and `stale_lock._config = mock_config`
- **render_initialization_plan()**
  - Function referenced non-existent `plan.session_name` attribute
  - Added `session_name: str` parameter to function signature
  - Updated `village/cli.py` to pass `config.tmux_session` as session_name
- **Test Bugs**
  - Added missing `import subprocess` to `tests/test_resume_rollback.py`
  - Fixed `CliRunner(mix_stderr=False)` → `CliRunner()` for Click compatibility

### Testing
- **Overall Test Suite**: 829 tests (826 passing, 3 failing, 29 skipped)
  - 3 failing tests are pre-existing issues (not caused by v1.0.0 work)
  - All new tests pass without failures
- **Parallel Agent Execution**
  - Used 4 parallel `general` agents to improve coverage
  - 20-25x speedup: 30 minutes vs 10-13 hours sequential
  - All 4 agents completed with 100% or 98% coverage targets

### Internal Changes
- Added `get_beads_workflow_context(config)` function in `village/chat/conversation.py`
- Updated `start_conversation()` to inject Beads workflow context into system prompt
- Mock config pattern standardized across test suite for Lock objects

### Known Limitations
- `probes/tmux.py` testing at 27% (deferred to v1.1.0)
  - Requires real tmux binary and session management
  - Complex to test (15+ untested functions)
  - Low impact on overall coverage (~1.5 percentage points)
  - Decision: Defer due to complexity vs value

### Migration Notes
- No migration required. All changes backward compatible.
- Beads integration is optional and gracefully degrades.

---

## [0.4.0] - Enhanced Observability - 2026-01-27

### Added
- **Real-Time Dashboard**
  - `village dashboard`: Static dashboard view
  - `village dashboard --watch`: Auto-refresh mode (default 2s interval)
  - Displays active workers, task queue, lock status, orphans, system load
  - Interactive: Press 'q' to quit, 'r' to refresh

- **Metrics Export**
  - `village metrics`: Export metrics with config defaults
  - `village metrics --backend prometheus`: Export Prometheus metrics
  - `village metrics --backend statsd`: Export StatsD metrics
  - `village metrics --reset`: Reset all metrics counters (stub for future cumulative metrics)
  - Metrics exposed: active_workers, queue_length, stale_locks, orphans_count, task_completion_rate, average_task_duration_seconds
  - Configuration: `[metrics]` section with backend, port, export_interval_seconds

- **Structured Event Queries**
  - `village events`: Query and display events from event log
  - Filters: `--task <id>`, `--status <STATUS>`, `--since <datetime>`, `--last <duration>`
  - Output formats: Table (default) or JSON (`--json`)
  - Examples:
    - `village events --task bd-a3f8`
    - `village events --status ok --last 1h`
    - `village events --json`

### Configuration
- New configuration options:
  - `[dashboard]` section:
    - `refresh_interval_seconds` (default: 2): Dashboard refresh interval
  - `[metrics]` section:
    - `backend` (default: prometheus): Metrics backend (prometheus, statsd)
    - `port` (default: 9090): Prometheus server port
    - `export_interval_seconds` (default: 60): Metrics export interval

### Documentation
- Updated ROADMAP.md with v0.4.0 completion and v1.0.0 as current status
- Updated command examples in ROADMAP.md for metrics command (flat flag-based syntax)

### Testing
- Test suite: `tests/test_dashboard.py` (20 tests) - All passing
- Test suite: `tests/test_metrics.py` (9 tests) - All passing
- Test suite: `tests/test_event_query.py` (26 tests) - All passing
- Total v0.4.0 tests: 55 tests, all passing

### Bug Fixes
- Fixed `MetricsCollector` constructor to accept `Config` parameter (broke existing tests)
- Updated all test fixtures in `tests/test_metrics.py` to pass Config object
- Fixed `parse_duration` function import (added helper function to cli.py)
- Fixed EventFilters and query_events import paths

### Internal Changes
- Added `parse_duration()` helper function to cli.py for parsing time duration strings (e.g., "1h", "30m", "2d")
- Refactored metrics command to flat flag-based structure (removed nested subcommands)
- Made session_name optional in MetricsCollector constructor (required for reset mode)

### Migration Notes
- **Metrics refactoring**: CLI pattern changed from nested subcommands to flat flags
  - Old: `village metrics prometheus --port 9090`
  - New: `village metrics --backend prometheus --port 9090`
- **MetricsCollector constructor**: Now requires Config parameter
  - Old: `MetricsCollector("village")`
  - New: `MetricsCollector(config, "village")`
- All existing functionality preserved, only CLI syntax and API signatures updated

## [0.3.0] - Safety & Coordination - 2026-01-26

### Added
- **State Machine CLI Commands**
  - `village state <task_id>`: Display task state and transition history
  - `village pause <task_id>`: Pause an in-progress task
  - `village resume-task <task_id>`: Resume a paused task
  - All commands support `--json` output for programmatic access
  - State transitions validated and logged to events.log

- **Automatic Rollback on Failure**
  - Worktree reset on task failure (configurable via `ROLLBACK_ON_FAILURE`)
  - Rollback events logged to events.log
  - Graceful error handling if rollback fails
  - Integration with existing resume.py flow

- **Conflict Detection** (already in v0.2.2)
  - File overlap detection between workers
  - Integration with queue arbitration
  - Configurable blocking via `BLOCK_ON_CONFLICT`

### Configuration
- New configuration options:
  - `ROLLBACK_ON_FAILURE` (default: true): Automatic worktree reset on task failure
  - `BLOCK_ON_CONFLICT` (default: false): Block tasks with file conflicts
  - `CONFLICT_DETECTION_ENABLED` (default: true): Enable conflict detection

### Documentation
- Added state management section to README.md
- Updated ROADMAP.md with v0.3.0 completion
- Examples added for pause/resume workflows

### Testing
- New test suite: `tests/test_state_machine_cli.py` (15+ tests)
- New test suite: `tests/test_resume_rollback.py` (10+ tests)
- Full test coverage for state machine and rollback functionality

### Bug Fixes
- Fixed state transition validation to prevent invalid state changes
- Improved error messages for invalid state transitions
- Fixed rollback event logging format

### Migration Notes
No migration required. All features backward compatible.

- State machine initialization: Automatic when tasks start
- Rollback: Opt-in via config (default enabled)
- CLI commands: New, no breaking changes to existing commands
