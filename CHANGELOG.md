# Changelog

All notable changes to Village will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased] - Task Decomposition & Extensibility

### Added
- **Automatic Task Decomposition**
  - LLM-based complexity detection evaluates if tasks should be broken down
  - Uses semantic understanding (not keyword matching) for flexibility
  - Sequential Thinking generates structured breakdown with dependencies
  - Dependencies displayed as task titles (not indices) for clarity
  - `/confirm` creates all subtasks with proper blocking relationships
  - `/edit` allows refining the entire breakdown
  - `/discard` skips decomposition, creates as single task
  - `/reset` alias for `/discard` command
- **Extensibility Framework**
  - 7 extension points for domain-specific customization without forking
  - ChatProcessor: Pre/post-process chat messages
  - ToolInvoker: Customize MCP tool invocation with caching
  - ThinkingRefiner: Domain-specific query refinement
  - ChatContext: Session state management
  - BeadsIntegrator: Custom task metadata
  - ServerDiscovery: Dynamic MCP server discovery
  - LLMProviderAdapter: LLM provider customization
- **Documentation**
  - Comprehensive EXTENSIBILITY_GUIDE.md (1596 lines, 7 tutorials)
  - EXTENSIBILITY_API.md for API reference
  - Research domain example in examples/research/
- **LLM Tools Module**
  - MCP tool mappings for Sequential Thinking, Atom of Thoughts, Think tool
  - ToolDefinitions with JSON schemas for prompts

### Fixed
- Beads CLI compatibility: removed unsupported `--status` flag
- Estimate conversion: string estimates ("days", "weeks") → minutes for `bd create`
- Delete requires `--force`: added to `bd delete` commands
- Lock directory creation: defensive `mkdir(parents=True, exist_ok=True)`
- JSON serialization: SessionStateEncoder handles datetime and dataclass objects
- Test suite: 41 failures reduced to 1 (97% reduction)

### Test Results
- Before: 1208 passed, 26 skipped, 41 failed
- After: 1242 passed, 26 skipped, 1 failed

## [Unreleased] - ST → AoT Light Strategy

### Added
- **Task Breakdown Strategy: ST → AoT Light**
  - New configuration-driven approach for task decomposition
  - Phase 1: Sequential Thinking for deep analysis (requirements, constraints, dependencies)
  - Phase 2: Atom of Thoughts (AoT-light) for atomic, queueable task creation
  - Default strategy: `st_aot_light` (configurable via env or config file)
  - Supported strategies: `sequential`, `atomic`, `st_aot_light`
- **Configuration Options**
  - Environment variable: `VILLAGE_TASK_BREAKDOWN_STRATEGY`
  - Config file key: `TASK_BREAKDOWN.STRATEGY`
  - New `TaskBreakdownConfig` dataclass with `from_env_and_config()` method
- **Tool Mapping**
  - Added `ATOM_OF_THOUGHTS` mapping (server="atom_of_thoughts", tool="AoT-light")
  - Added `ATOM_OF_THOUGHTS_TOOL` definition with JSON schema for prompts
  - Tool name format: `mcproxy_{server}__{tool}` pattern
- **Prompt Builders**
  - `_build_st_analysis_prompt()`: Creates analysis-focused Sequential Thinking prompt
  - `_build_aot_light_atomization_prompt()`: Creates atomic task atomization prompt
  - Both support `beads_state` context for dependency awareness
- **Strategy Router**
  - `generate_task_breakdown()` now routes based on `config.task_breakdown.strategy`
  - `_st_aot_light_strategy()`: Orchestrates two-phase analysis → atomization workflow
  - Graceful fallback to original sequential behavior for unknown strategies
- **Bug Fixes**
  - Added missing `@dataclass` decorator to `ExtensionConfig` class
  - Added `from_env_and_config()` method to `ExtensionConfig` for consistency

### Testing
- **New Test Files**
  - `tests/test_config/task_breakdown.py`: 10 tests for TaskBreakdownConfig
  - `tests/test_llm_tools_atom_of_thoughts.py`: 9 tests for AoT tool mappings
  - `tests/test_chat/test_sequential_thinking_aot_light.py`: 10 tests for strategy
- **Total Tests**: 29 new tests, all passing

### Files Modified
- `village/config.py`: Added TaskBreakdownConfig, fixed ExtensionConfig
- `village/llm/tools.py`: Added ATOM_OF_THOUGHTS mappings and tool definition
- `village/chat/sequential_thinking.py`: Added prompt builders and strategy router

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
