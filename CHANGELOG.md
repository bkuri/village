# Changelog

All notable changes to Village will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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
