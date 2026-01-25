# Changelog

All notable changes to Village are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

## [1.2.0] - 2026-01-24

### Added

#### Event Logging
- Automatic event logging to `.village/events.log` in NDJSON format
- All operations logged with timestamps, task IDs, commands, and results
- Post-mortem analysis and crash recovery support

#### Queue Deduplication
- Tasks blocked from running twice within configurable TTL (default: 5 min)
- `--force` flag to override deduplication when needed
- `QUEUE_TTL_MINUTES` config option and `VILLAGE_QUEUE_TTL_MINUTES` env var

#### Enhanced Cleanup
- `--apply` flag to remove orphan and stale worktrees
- Separate tracking of orphan_worktrees and stale_worktrees in CleanupPlan
- Safer corrupted lock handling with automatic logging

#### Expanded JSON Output
- `queue --plan --json` includes full lock details (pane_id, window, agent, claimed_at)
- Workspace paths included in JSON output
- Better dry-run validation and scheduling visibility

#### Testing
- 58 new SCM tests (protocol compliance, Git backend, JJ placeholders)
- 3 v1.2 integration tests (event logging, deduplication, cleanup)
- Coverage: 74% overall (git.py: 85%, protocol: 100%)

### Fixed

- Timezone handling in event timestamps (now uses `datetime.now(timezone.utc)`)

### Configuration

- New config option: `QUEUE_TTL_MINUTES` (default: 5)
- New env var: `VILLAGE_QUEUE_TTL_MINUTES`

### Migration Notes

No migration required. All features backward compatible and opt-in.

## [1.1.0] - 2026-01-XX

### Added

- SCM abstraction layer with Git backend
- Pluggable system for future SCM backends (e.g., Jujutsu)

### Changed

- All workspace operations now use SCM abstraction
- Git-specific commands isolated to `village/scm/git.py`

### Migration Notes

No migration required. Existing workflows work identically.
