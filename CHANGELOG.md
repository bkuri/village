# Changelog

All notable changes to Village will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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
