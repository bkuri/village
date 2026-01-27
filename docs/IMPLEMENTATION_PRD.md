# Village - Parallelization Implementation PRD

## Purpose

This PRD defines a parallelized implementation strategy for Village's roadmap (v0.3.0 → v1.1.0), using subagents to accelerate development by working on independent modules simultaneously.

**Objective**: Reduce total implementation time from ~84-104 hours (sequential) to ~58-77 hours (parallelized), achieving 25-30% time savings while maintaining code quality and ensuring proper integration.

---

## Parallelization Strategy

### Core Principles

1. **Module Independence**: Each feature module is self-contained with clear interfaces
2. **Concurrent Development**: Multiple subagents work on independent codebases simultaneously
3. **Sequential Integration**: Integration tasks require core modules to complete first
4. **Quality Assurance**: Each module tested independently before integration
5. **Coordination Protocol**: Clear handoff between subagents and integration phase

### Development Pattern

```
Parallel Phase (Subagents)
   ├── Subagent 1: Module A
   ├── Subagent 2: Module B
   └── Subagent 3: Module C
         ↓
Sequential Integration Phase
   ├── Integrate Module A
   ├── Integrate Module B
   └── Integrate Module C
         ↓
Testing & Validation Phase
   ├── Test integrated modules
   ├── E2E workflow testing
   └── Bug fixes & stabilization
```

### Success Factors

- **Clear Module Boundaries**: Well-defined interfaces between modules
- **Minimal Cross-Module Dependencies**: Core modules don't depend on each other
- **Simple Integration Surface**: Single-point integration (config, CLI, event log)
- **Comprehensive Testing**: Unit tests for each module, integration tests for workflows
- **Continuous Validation**: Each phase validated before proceeding

---

## Phase 1: v0.3.0 - Safety & Coordination

### Objective

Implement core safety and coordination features (state machine, conflict detection, automatic rollback) in parallel.

### Parallel Tasks (2 Subagents)

#### Subagent 1: State Machine Module

**Module**: `village/state_machine.py` (~200 lines)

**Responsibilities**:
- Define task lifecycle states (QUEUED, CLAIMED, IN_PROGRESS, PAUSED, COMPLETED, FAILED)
- Implement state transition validation logic
- State persistence (read/write to lock files)
- Event logging for all state transitions

**Interface**:
```python
class TaskStateMachine:
    def transition(self, task_id: str, new_state: TaskState, context: dict) -> TransitionResult
    def get_state(self, task_id: str) -> TaskState | None
    def get_state_history(self, task_id: str) -> list[StateTransition]
    def can_transition(self, from_state: TaskState, to_state: TaskState) -> bool
```

**Acceptance Criteria**:
- [ ] All valid state transitions implemented
- [ ] Invalid transitions rejected with clear error messages
- [ ] State persisted to lock files
- [ ] All transitions logged to events.log
- [ ] Unit tests >85% coverage
- [ ] Type hints and docstrings complete
- [ ] Follow Village code style (AGENTS.md)

**Deliverables**:
- `village/state_machine.py` (module)
- `tests/test_state_machine.py` (unit tests)
- Documentation (docstrings, README section)

**Estimated Time**: 6-8 hours

---

#### Subagent 2: Conflict Detection Module

**Module**: `village/conflict_detection.py` (~150 lines)

**Responsibilities**:
- Detect file overlap between active workers
- Parse git/jj status to identify modified files
- Report potential conflicts before task execution
- Provide conflict warnings (optional blocking on config)

**Interface**:
```python
def detect_file_conflicts(active_workers: list[WorkerInfo]) -> ConflictReport
def get_modified_files(worktree_path: Path) -> list[Path]
def find_overlaps(files: list[Path]) -> list[Conflict]
```

**Acceptance Criteria**:
- [ ] File overlap detection works correctly
- [ ] Git/jj status parsing accurate
- [ ] Conflict reports include actionable details
- [ ] Optional blocking via config (BLOCK_ON_CONFLICT)
- [ ] Integration with queue.py (check before claiming)
- [ ] Unit tests >80% coverage
- [ ] Type hints and docstrings complete
- [ ] Follow Village code style

**Deliverables**:
- `village/conflict_detection.py` (module)
- `tests/test_conflicts.py` (unit tests)
- Documentation (docstrings, README section)

**Estimated Time**: 4-6 hours

---

### Sequential Integration Tasks

#### Integration Task 1: Config Updates

**Module**: `village/config.py`

**Responsibilities**:
- Add config options for rollback behavior
- Add config options for conflict detection
- Document new config options

**Config Options**:
```ini
# Rollback behavior
[DEFAULT]
ROLLBACK_ON_FAILURE=true

# Conflict detection
[DEFAULT]
BLOCK_ON_CONFLICT=false
CONFLICT_DETECTION_ENABLED=true
```

**Acceptance Criteria**:
- [ ] New config options added and documented
- [ ] Config parsing validated
- [ ] Environment variables supported (VILLAGE_ROLLBACK_ON_FAILURE)
- [ ] Config defaults documented in README

**Estimated Time**: 1 hour

**Dependencies**: None

---

#### Integration Task 2: Queue Integration

**Module**: `village/queue.py`

**Responsibilities**:
- Integrate conflict detection before claiming tasks
- Integrate state machine for state tracking
- Update lock files with state information
- Add warning output for conflicts

**Integration Points**:
```python
# Before claiming task
conflicts = detect_file_conflicts(active_workers)
if conflicts.has_conflicts():
    if config.BLOCK_ON_CONFLICT:
        return "blocked_by_conflict"
    else:
        warn(f"Potential conflicts: {conflicts}")

# After claiming task
state_machine.transition(task_id, "CLAIMED", context={...})
```

**Acceptance Criteria**:
- [ ] Conflict detection integrated before claiming
- [ ] State machine integrated after claiming
- [ ] Lock files include state information
- [ ] Conflict warnings displayed in CLI
- [ ] Integration tests passing
- [ ] Documentation updated (queue command help)

**Estimated Time**: 3-4 hours

**Dependencies**: state_machine.py, conflict_detection.py, config.py updates

---

#### Integration Task 3: Resume Rollback Logic

**Module**: `village/resume.py`

**Responsibilities**:
- Wrap OpenCode execution in try/except
- On failure: reset worktree to clean state
- On failure: mark task as FAILED in state machine
- On failure: log rollback events to events.log

**Integration Points**:
```python
try:
    # Execute OpenCode
    result = execute_opencode(...)
    state_machine.transition(task_id, "COMPLETED", context={...})
except Exception as e:
    # Rollback
    rollback_worktree(task_id, worktree_path)
    state_machine.transition(task_id, "FAILED", context={"error": str(e)})
    log_rollback_event(task_id, e)
```

**Acceptance Criteria**:
- [ ] Automatic rollback on OpenCode failure
- [ ] Worktree reset to clean state
- [ ] State updated to FAILED
- [ ] Rollback events logged to events.log
- [ ] Config option to disable rollback (ROLLBACK_ON_FAILURE=false)
- [ ] Integration tests passing
- [ ] Documentation updated (resume command help)

**Estimated Time**: 3-4 hours

**Dependencies**: state_machine.py, config.py updates

---

### Phase 1 Testing & Validation

**Responsibilities**:
- Run full test suite: `uv run pytest`
- Verify test coverage >85% for new modules
- E2E testing of rollback and conflict detection workflows
- Bug fixes and stabilization

**Test Scenarios**:
1. State machine transitions (valid and invalid)
2. Conflict detection with multiple workers
3. Automatic rollback on OpenCode failure
4. Config option validation
5. Integration with queue and resume

**Acceptance Criteria**:
- [ ] All tests passing
- [ ] Test coverage >85% overall, >90% for critical modules
- [ ] E2E workflows tested and passing
- [ ] No critical bugs
- [ ] Documentation updated

**Estimated Time**: 2-3 hours

**Dependencies**: All integration tasks complete

---

### Phase 1 Summary

| Component | Subagent | Sequential | Total Time |
|-----------|-----------|------------|------------|
| State Machine | 6-8 hrs | - | 6-8 hrs |
| Conflict Detection | 4-6 hrs | - | 4-6 hrs |
| Config Updates | - | 1 hr | 1 hr |
| Queue Integration | - | 3-4 hrs | 3-4 hrs |
| Resume Rollback | - | 3-4 hrs | 3-4 hrs |
| Testing & Validation | - | 2-3 hrs | 2-3 hrs |
| **Total** | **10-14 hrs** | **9-12 hrs** | **19-26 hrs** |

**Parallel Time**: 10-14 hrs (parallel tasks) + 9-12 hrs (sequential) = **19-26 hrs**
**Sequential Time**: 16-20 hrs (if all tasks sequential)
**Time Savings**: 3-6 hours (19-26% reduction)

---

## Phase 2: v0.4.0 - Enhanced Observability

### Objective

Implement observability features (real-time dashboard, metrics export, event queries) in parallel.

### Parallel Tasks (3 Subagents)

#### Subagent 1: Metrics Module

**Module**: `village/metrics.py` (~200 lines)

**Responsibilities**:
- Collect Village metrics (workers, queue, locks, orphans)
- Export to Prometheus (HTTP endpoint)
- Export to StatsD (UDP socket)
- Metrics configuration and management

**Interface**:
```python
class MetricsCollector:
    def collect_metrics(self) -> MetricsReport
    def export_prometheus(self) -> PrometheusMetrics
    def export_statsd(self) -> StatsDMetrics
    def start_prometheus_server(self, port: int)
    def start_statsd_client(self, host: str, port: int)
```

**Metrics**:
- `village_active_workers` (gauge)
- `village_queue_length` (gauge)
- `village_stale_locks` (gauge)
- `village_orphans_count` (gauge)
- `village_task_completion_rate` (histogram)
- `village_average_task_duration_seconds` (histogram)

**Acceptance Criteria**:
- [ ] All metrics collected accurately
- [ ] Prometheus HTTP endpoint functional
- [ ] StatsD UDP client functional
- [ ] Metrics export interval configurable
- [ ] Unit tests >80% coverage
- [ ] Integration with Village state (workers, locks, orphans)
- [ ] Type hints and docstrings complete
- [ ] Follow Village code style

**Deliverables**:
- `village/metrics.py` (module)
- `tests/test_metrics.py` (unit tests)
- Documentation (docstrings, metrics catalog)

**Estimated Time**: 4-6 hours

---

#### Subagent 2: Event Query Module

**Module**: `village/event_query.py` (~150 lines)

**Responsibilities**:
- Parse NDJSON events.log
- Filter events by task, status, time range
- Format output (JSON, table)
- CLI integration for query command

**Interface**:
```python
def query_events(
    filters: EventFilters,
    format: Literal["json", "table"]
) -> QueryResult

class EventFilters:
    task_id: str | None
    status: str | None
    since: datetime | None
    last: timedelta | None
```

**Acceptance Criteria**:
- [ ] Event log parsing accurate
- [ ] Filters work correctly (task, status, time range)
- [ ] JSON output valid and parseable
- [ ] Table output readable and formatted
- [ ] CLI command `village events` working
- [ ] Unit tests >80% coverage
- [ ] Integration with events.log
- [ ] Type hints and docstrings complete
- [ ] Follow Village code style

**Deliverables**:
- `village/event_query.py` (module)
- `tests/test_event_query.py` (unit tests)
- Documentation (docstrings, CLI help)

**Estimated Time**: 3-4 hours

---

#### Subagent 3: Dashboard Module

**Module**: `village/dashboard.py` (~300 lines)

**Responsibilities**:
- Create real-time terminal UI dashboard
- Display active workers, task queue, lock status
- Auto-refresh every 2 seconds (configurable)
- Interactive controls (quit, refresh)

**Interface**:
```python
class VillageDashboard:
    def start_watch_mode(self, refresh_interval: int = 2)
    def refresh_display(self)
    def quit(self)
```

**Display Components**:
- Active Workers table (TASK_ID, STATUS, AGENT, PANE, WINDOW)
- Task Queue (ready tasks, blocked tasks)
- Lock Status (ACTIVE, STALE, orphans)
- System Load (load average, max workers)

**Acceptance Criteria**:
- [ ] Real-time dashboard displays correctly
- [ ] Auto-refresh functional
- [ ] Interactive controls (q to quit, r to refresh)
- [ ] Display components accurate and up-to-date
- [ ] CLI command `village dashboard --watch` working
- [ ] Unit tests >75% coverage (mocked terminal UI)
- [ ] Integration with Village state (workers, locks, orphans)
- [ ] Type hints and docstrings complete
- [ ] Follow Village code style

**Deliverables**:
- `village/dashboard.py` (module)
- `tests/test_dashboard.py` (unit tests)
- Documentation (docstrings, CLI help)

**Estimated Time**: 4-5 hours

---

### Sequential Integration Tasks

#### Integration Task 1: Config Updates

**Module**: `village/config.py`

**Responsibilities**:
- Add config options for metrics export
- Add config options for dashboard

**Config Options**:
```ini
# Metrics
[metrics]
backend=prometheus
port=9090
export_interval_seconds=60
statsd_host=localhost
statsd_port=8125

# Dashboard
[dashboard]
refresh_interval_seconds=2
enabled=true
```

**Acceptance Criteria**:
- [ ] New config options added and documented
- [ ] Config parsing validated
- [ ] Environment variables supported
- [ ] Config defaults documented in README

**Estimated Time**: 1 hour

**Dependencies**: None

---

#### Integration Task 2: CLI Integration

**Module**: `village/cli.py`

**Responsibilities**:
- Add CLI commands: `dashboard`, `events`, `metrics export`
- Add flags and options for each command
- Wire commands to module functions

**CLI Commands**:
```bash
village dashboard --watch --refresh-interval 2
village events --task bd-a3f8 --last 1h --json
village metrics export --backend prometheus --port 9090
```

**Acceptance Criteria**:
- [ ] All CLI commands functional
- [ ] Help text complete and accurate
- [ ] Flags and options working
- [ ] JSON output valid (for events)
- [ ] Integration with modules tested
- [ ] Documentation updated (CLI help text)

**Estimated Time**: 2-3 hours

**Dependencies**: All modules (metrics, event_query, dashboard)

---

#### Integration Task 3: Event Log Integration

**Module**: `village/event_log.py`

**Responsibilities**:
- Ensure events are structured for querying
- Add metrics-specific events (metrics_exported, etc.)
- Add dashboard refresh events

**Event Structure**:
```json
{
  "ts": "2026-01-26T10:00:00Z",
  "cmd": "metrics_export",
  "backend": "prometheus",
  "result": "ok"
}
```

**Acceptance Criteria**:
- [ ] Events structured for querying
- [ ] Metrics export events logged
- [ ] Dashboard refresh events logged
- [ ] No breaking changes to existing events.log format
- [ ] Integration with event_query.py tested

**Estimated Time**: 1-2 hours

**Dependencies**: metrics.py, event_query.py, dashboard.py

---

### Phase 2 Testing & Validation

**Responsibilities**:
- Run full test suite: `uv run pytest`
- Verify test coverage >80% for new modules
- E2E testing of observability workflows
- Bug fixes and stabilization

**Test Scenarios**:
1. Metrics collection and export (Prometheus, StatsD)
2. Event queries with various filters
3. Dashboard refresh and display accuracy
4. CLI command integration
5. Event log querying

**Acceptance Criteria**:
- [ ] All tests passing
- [ ] Test coverage >80% for new modules
- [ ] E2E workflows tested and passing
- [ ] No critical bugs
- [ ] Documentation updated

**Estimated Time**: 2-3 hours

**Dependencies**: All integration tasks complete

---

### Phase 2 Summary

| Component | Subagent | Sequential | Total Time |
|-----------|-----------|------------|------------|
| Metrics Module | 4-6 hrs | - | 4-6 hrs |
| Event Query Module | 3-4 hrs | - | 3-4 hrs |
| Dashboard Module | 4-5 hrs | - | 4-5 hrs |
| Config Updates | - | 1 hr | 1 hr |
| CLI Integration | - | 2-3 hrs | 2-3 hrs |
| Event Log Integration | - | 1-2 hrs | 1-2 hrs |
| Testing & Validation | - | 2-3 hrs | 2-3 hrs |
| **Total** | **11-15 hrs** | **6-9 hrs** | **17-24 hrs** |

**Parallel Time**: 11-15 hrs (parallel tasks) + 6-9 hrs (sequential) = **17-24 hrs**
**Sequential Time**: 12-16 hrs (if all tasks sequential)
**Time Savings**: 2-4 hours (13-20% reduction)

---

## Phase 3: v0.3.0 + v0.4.0 Comprehensive Testing

### Objective

Comprehensive E2E testing, cross-version integration, bug fixes, and stabilization for v0.3.0 and v0.4.0 features.

### Testing Tasks (1 Agent)

#### Task 1: E2E Workflow Testing

**Responsibilities**:
- Test state machine workflows (pause/resume, transitions)
- Test conflict detection scenarios (multiple workers, file overlaps)
- Test automatic rollback on OpenCode failure
- Test observability features (dashboard, metrics, event queries)
- Test integrated workflows (queue → status → resume → events)

**Test Scenarios**:
1. State machine: Transition all states, validate invalid transitions
2. Conflict detection: Two workers modifying same files
3. Rollback: Simulate OpenCode failure, verify worktree reset
4. Dashboard: Start dashboard, verify refresh, verify accuracy
5. Metrics: Export metrics, verify Prometheus endpoint
6. Event queries: Query events with various filters
7. Integrated: Full workflow from queue to completion

**Acceptance Criteria**:
- [ ] All E2E test scenarios passing
- [ ] State machine transitions validated
- [ ] Conflict detection working correctly
- [ ] Rollback recovering from failures
- [ ] Dashboard displaying accurate state
- [ ] Metrics exporting correctly
- [ ] Event queries filtering correctly

**Estimated Time**: 3-4 hours

---

#### Task 2: Cross-Version Integration Testing

**Responsibilities**:
- Test v0.3.0 features integrate with v0.4.0 features
- Test state machine + metrics integration
- Test conflict detection + dashboard integration
- Test rollback + event log integration
- Test config options across all features

**Integration Scenarios**:
1. State machine state transitions → metrics collection
2. Conflict detection → dashboard warning display
3. Rollback → event log entry → event query
4. Config options (rollback, conflicts, metrics, dashboard)
5. CLI commands working together

**Acceptance Criteria**:
- [ ] Cross-version integration working correctly
- [ ] No breaking changes between versions
- [ ] All config options validated
- [ ] All CLI commands functional

**Estimated Time**: 2-3 hours

---

#### Task 3: Bug Fixes & Stabilization

**Responsibilities**:
- Fix any bugs found during testing
- Stabilize flaky tests
- Performance tuning (dashboard refresh, metrics export)
- Edge case handling (empty state, missing files, etc.)

**Bug Categories**:
- Race conditions (state transitions, metrics collection)
- Edge cases (no workers, no events, empty queue)
- Performance (dashboard refresh overhead, metrics export latency)
- Error handling (invalid config, missing files, network errors)

**Acceptance Criteria**:
- [ ] All critical bugs fixed
- [ ] Flaky tests stabilized
- [ ] Performance acceptable (dashboard <100ms refresh, metrics <1s export)
- [ ] Edge cases handled gracefully
- [ ] Error messages clear and actionable

**Estimated Time**: 2-3 hours

---

### Phase 3 Summary

| Component | Subagent | Sequential | Total Time |
|-----------|-----------|------------|------------|
| E2E Workflow Testing | - | 3-4 hrs | 3-4 hrs |
| Cross-Version Integration Testing | - | 2-3 hrs | 2-3 hrs |
| Bug Fixes & Stabilization | - | 2-3 hrs | 2-3 hrs |
| **Total** | - | **7-10 hrs** | **7-10 hrs** |

**Total Time**: 7-10 hours (all tasks sequential, but focused on testing and stabilization)

---

## Phase 4: v1.0.0 - Production-Ready

### Objective

Prepare Village for production release: audit trails emphasis, test coverage improvement, documentation completion, zero critical bugs.

### Parallel Tasks (3 Subagents)

#### Subagent 1: Documentation Updates

**Modules**: README.md, PRD.md, docs/examples/, docs/troubleshooting.md

**Responsibilities**:
- Complete README with all v0.3.0 and v0.4.0 features
- Complete PRD with success criteria and audit guarantees
- Create example workflows (state machine, conflict detection, rollback, dashboard, metrics)
- Create troubleshooting guide (common issues, solutions)
- Update CHANGELOG.md with v0.3.0 and v0.4.0 features

**Documentation Sections**:
- README: New features, examples, troubleshooting
- PRD: Success criteria, audit guarantees, production readiness
- Examples: Step-by-step workflows for new features
- Troubleshooting: Common issues, error messages, solutions
- CHANGELOG: Complete changelog for v0.3.0 and v0.4.0

**Acceptance Criteria**:
- [ ] README comprehensive with all features
- [ ] PRD success criteria complete
- [ ] Example workflows clear and accurate
- [ ] Troubleshooting guide covers common issues
- [ ] CHANGELOG.md complete and accurate
- [ ] All documentation tested for accuracy

**Estimated Time**: 5-6 hours

---

#### Subagent 2: Test Coverage Improvement

**Modules**: tests/ (all test files)

**Responsibilities**:
- Add missing tests for edge cases
- Target >85% overall coverage
- Target >90% coverage for critical modules (queue, resume, locks, state_machine)
- Test integration workflows (state machine + queue, conflict detection + resume, etc.)
- Add performance tests (metrics export, dashboard refresh)

**Test Targets**:
- state_machine.py: >90% coverage
- conflict_detection.py: >90% coverage
- metrics.py: >85% coverage
- event_query.py: >85% coverage
- dashboard.py: >80% coverage
- Overall: >85% coverage

**Acceptance Criteria**:
- [ ] Test coverage >85% overall
- [ ] Critical modules >90% coverage
- [ ] Edge cases tested
- [ ] Integration workflows tested
- [ ] Performance tests added
- [ ] All tests passing

**Estimated Time**: 5-7 hours

---

#### Subagent 3: Bug Fixes & Stabilization

**Modules**: village/ (all modules)

**Responsibilities**:
- Fix any critical bugs found during v0.3.0 and v0.4.0 development
- Ensure zero exit code 1 crashes
- Stabilize flaky tests
- Performance tuning (metrics export, dashboard refresh, state transitions)
- Error handling improvements (clear messages, graceful degradation)

**Bug Categories**:
- Critical bugs (exit code 1 crashes)
- Race conditions (state transitions, metrics collection)
- Performance issues (slow dashboard, metrics export latency)
- Error handling (invalid config, missing files, network errors)

**Acceptance Criteria**:
- [ ] Zero critical bugs (exit code 1)
- [ ] Flaky tests stabilized
- [ ] Performance acceptable (dashboard <100ms, metrics <1s)
- [ ] Error messages clear and actionable
- [ ] Graceful degradation on errors

**Estimated Time**: 4-6 hours

---

### Sequential Integration Tasks

#### Integration Task 1: Validation Testing

**Responsibilities**:
- E2E testing of complete workflows (v0.3.0 + v0.4.0 + v1.0.0)
- Cross-version compatibility testing
- Migration path validation (v0.2.x → v1.0.0)
- Performance benchmarking

**Test Scenarios**:
1. Complete workflow: up → queue → status → resume → dashboard → events → metrics
2. State machine transitions in production-like scenario
3. Conflict detection with multiple workers
4. Automatic rollback on failure
5. Dashboard refresh under load
6. Metrics export under load
7. Event queries with large event logs
8. Migration from v0.2.3 to v1.0.0

**Acceptance Criteria**:
- [ ] All E2E workflows passing
- [ ] Cross-version compatibility verified
- [ ] Migration path tested and working
- [ ] Performance benchmarks documented
- [ ] No critical bugs in production scenarios

**Estimated Time**: 3-4 hours

**Dependencies**: All subagent tasks complete

---

#### Integration Task 2: Release Checklist Validation

**Responsibilities**:
- Validate v1.0.0 release checklist (from PRD.md)
- Document any checklist items not met
- Create plan to complete any missing items

**v1.0.0 Release Checklist**:
- [x] State machine workflows working
- [x] Automatic rollback functional
- [x] Conflict detection operational
- [x] Real-time dashboard functional
- [x] Metrics export working
- [x] Event queries operational
- [ ] Test coverage >85% overall
- [ ] Zero critical bugs in production
- [ ] Documentation complete (README, PRD, examples, troubleshooting)
- [ ] CHANGELOG.md up-to-date
- [ ] Audit trails comprehensive

**Acceptance Criteria**:
- [ ] All v1.0.0 checklist items validated
- [ ] Missing items documented
- [ ] Plan created to complete missing items (if any)

**Estimated Time**: 1-2 hours

**Dependencies**: Validation testing complete

---

### Phase 4 Summary

| Component | Subagent | Sequential | Total Time |
|-----------|-----------|------------|------------|
| Documentation Updates | 5-6 hrs | - | 5-6 hrs |
| Test Coverage Improvement | 5-7 hrs | - | 5-7 hrs |
| Bug Fixes & Stabilization | 4-6 hrs | - | 4-6 hrs |
| Validation Testing | - | 3-4 hrs | 3-4 hrs |
| Release Checklist Validation | - | 1-2 hrs | 1-2 hrs |
| **Total** | **14-19 hrs** | **4-6 hrs** | **18-25 hrs** |

**Parallel Time**: 14-19 hrs (parallel tasks) + 4-6 hrs (sequential) = **18-25 hrs**
**Sequential Time**: 24-28 hrs (if all tasks sequential)
**Time Savings**: 6-10 hours (25-31% reduction)

---

## Phase 5: v1.1.0 - High-ROI Integrations

### Objective

Implement high-ROI integrations (E2E tests, GitHub integration, CI/CD hooks, notifications) in parallel.

### Parallel Tasks (4 Subagents)

#### Subagent 1: E2E Test Suite

**Module**: `tests/test_e2e.py` (600-800 lines)

**Responsibilities**:
- Create comprehensive E2E test suite
- Test onboarding workflow (new user → setup → first task)
- Test multi-task execution (queue 3 tasks, verify workers)
- Test crash recovery (kill tmux, detect orphans, cleanup)
- Test concurrency (parallel queue from 2 terminals, verify no duplicates)
- Test full user journey (new project → complete workflow → cleanup)

**Test Classes**:
```python
class TestOnboardingE2E:
    def test_new_project_workflow()
    def test_first_task_execution()
    def test_status_after_setup()

class TestMultiTaskExecutionE2E:
    def test_queue_creates_three_workers()
    def test_concurrency_limits_enforced()
    def test_lock_files_correct()

class TestCrashRecoveryE2E:
    def test_tmux_crash_creates_orphans()
    def test_cleanup_removes_orphans()
    def test_event_log_crashes_recorded()

class TestConcurrencyE2E:
    def test_parallel_queue_no_duplicates()
    def test_lock_arbitration_active_stale()
    def test_stale_lock_stealing()

class TestFullUserJourneyE2E:
    def test_complete_lifecycle()
    def test_cleanup_workflow()
    def test_event_log_complete()
```

**Acceptance Criteria**:
- [ ] E2E test suite with 30+ tests
- [ ] All E2E tests passing
- [ ] Onboarding workflow validated
- [ ] Multi-task execution tested
- [ ] Crash recovery tested
- [ ] Concurrency tested
- [ ] Full user journey tested
- [ ] Type hints and docstrings complete
- [ ] Follow Village code style

**Deliverables**:
- `tests/test_e2e.py` (E2E test suite)
- Documentation (test scenarios, fixtures)

**Estimated Time**: 10-12 hours

---

#### Subagent 2: GitHub Integration

**Module**: `village/github_integration.py` (~250 lines)

**Responsibilities**:
- Generate PR descriptions from task metadata + git diff
- Sync PR status with Beads task completion
- Add PR labels based on task metadata
- GitHub CLI integration

**Interface**:
```python
def generate_pr_description(task_id: str, worktree_path: Path) -> PRDescription
def sync_pr_status(task_id: str, pr_number: int) -> SyncResult
def add_pr_labels(pr_number: int, labels: list[str]) -> None

class PRDescription:
    summary: str
    changes: str
    testing_checklist: list[str]
    related_tasks: list[str]
```

**Acceptance Criteria**:
- [ ] PR description generation working correctly
- [ ] PR status sync functional
- [ ] PR labels added based on task metadata
- [ ] GitHub CLI integration working
- [ ] Integration with Beads task data
- [ ] Integration with git diff parsing
- [ ] Unit tests >75% coverage
- [ ] Type hints and docstrings complete
- [ ] Follow Village code style

**Deliverables**:
- `village/github_integration.py` (module)
- `tests/test_github.py` (unit tests)
- Documentation (docstrings, CLI help)

**Estimated Time**: 6-8 hours

---

#### Subagent 3: CI/CD Hooks

**Module**: `village/ci_integration.py` (~200 lines)

**Responsibilities**:
- Trigger CI/CD builds on task completion
- Monitor build status
- Update task status on build failure
- Integration with GitHub Actions, GitLab CI, Jenkins

**Interface**:
```python
def trigger_build(task_id: str, platform: Literal["github_actions", "gitlab_ci", "jenkins"]) -> BuildResult
def monitor_build(build_id: str) -> BuildStatus
def update_task_on_failure(task_id: str, build_id: str, reason: str) -> None
```

**Acceptance Criteria**:
- [ ] Build triggers functional (GitHub Actions, GitLab CI, Jenkins)
- [ ] Build status monitoring working
- [ ] Task status updated on build failure
- [ ] Integration with Village task completion events
- [ ] Config options for CI/CD platforms
- [ ] Unit tests >75% coverage
- [ ] Type hints and docstrings complete
- [ ] Follow Village code style

**Deliverables**:
- `village/ci_integration.py` (module)
- `tests/test_ci.py` (unit tests)
- Documentation (docstrings, config options)

**Estimated Time**: 5-6 hours

---

#### Subagent 4: Notification Systems

**Module**: `village/notifications.py` (~180 lines)

**Responsibilities**:
- Webhook support (Slack, Discord, Email)
- Event-based triggers (task_failed, orphan_detected, high_priority_task)
- Configurable event filters
- Webhook delivery with retry logic

**Interface**:
```python
def send_notification(event: NotificationEvent, backend: NotificationBackend) -> NotificationResult
class NotificationBackend:
    webhook_url: str
    events: list[str]

class NotificationEvent:
    event_type: str
    task_id: str | None
    timestamp: datetime
    context: dict
```

**Acceptance Criteria**:
- [ ] Webhook delivery working (Slack, Discord, Email)
- [ ] Event triggers functional
- [ ] Configurable event filters working
- [ ] Retry logic for failed webhooks
- [ ] Integration with Village event log
- [ ] Unit tests >75% coverage
- [ ] Type hints and docstrings complete
- [ ] Follow Village code style

**Deliverables**:
- `village/notifications.py` (module)
- `tests/test_notifications.py` (unit tests)
- Documentation (docstrings, config examples)

**Estimated Time**: 4-5 hours

---

### Sequential Integration Tasks

#### Integration Task 1: Config Updates

**Module**: `village/config.py`

**Responsibilities**:
- Add config options for GitHub integration
- Add config options for CI/CD hooks
- Add config options for notification systems

**Config Options**:
```ini
# GitHub
[github]
enabled=true
pr_description_enabled=true
status_sync_enabled=true

# CI/CD
[ci.github_actions]
enabled=true
trigger_on_task_complete=true
notify_on_failure=true

[notifications.slack]
enabled=true
webhook_url=https://hooks.slack.com/services/...
events=task_failed,orphan_detected,high_priority_task
```

**Acceptance Criteria**:
- [ ] New config options added and documented
- [ ] Config parsing validated
- [ ] Environment variables supported
- [ ] Config defaults documented in README

**Estimated Time**: 2-3 hours

**Dependencies**: None

---

#### Integration Task 2: Event Log Integration

**Module**: `village/event_log.py`

**Responsibilities**:
- Hook event logging for GitHub integration events
- Hook event logging for CI/CD build events
- Hook event logging for notification events

**Event Structure**:
```json
{
  "ts": "2026-01-26T10:00:00Z",
  "cmd": "pr_description_generated",
  "task_id": "bd-a3f8",
  "pr_number": 123,
  "result": "ok"
}
```

**Acceptance Criteria**:
- [ ] GitHub integration events logged
- [ ] CI/CD build events logged
- [ ] Notification events logged
- [ ] No breaking changes to existing events.log format
- [ ] Integration with all integration modules tested

**Estimated Time**: 2-3 hours

**Dependencies**: github_integration.py, ci_integration.py, notifications.py

---

#### Integration Task 3: CLI Integration

**Module**: `village/cli.py`

**Responsibilities**:
- Add CLI commands: `pr describe`, `pr sync`, `ci trigger`, `notifications test`
- Add flags and options for each command
- Wire commands to module functions

**CLI Commands**:
```bash
village pr describe bd-a3f8
village pr sync --from-beads
village ci trigger --task bd-a3f8 --platform github_actions
village notifications test --backend slack
```

**Acceptance Criteria**:
- [ ] All CLI commands functional
- [ ] Help text complete and accurate
- [ ] Flags and options working
- [ ] Integration with modules tested
- [ ] Documentation updated (CLI help text)

**Estimated Time**: 2-3 hours

**Dependencies**: github_integration.py, ci_integration.py, notifications.py, config.py

---

### Phase 5 Testing & Validation

**Responsibilities**:
- Run full test suite: `uv run pytest`
- Verify test coverage >75% for integration modules
- E2E testing of integration workflows
- Bug fixes and stabilization

**Test Scenarios**:
1. E2E test suite (30+ tests) all passing
2. GitHub PR description generation and sync
3. CI/CD build triggers and status updates
4. Notification webhooks (Slack, Discord, Email)
5. Integration workflows (queue → PR → CI → notification)
6. Config validation for all integrations
7. Event log querying with new events

**Acceptance Criteria**:
- [ ] All tests passing (including E2E suite)
- [ ] Test coverage >75% for integration modules
- [ ] E2E integration workflows tested and passing
- [ ] No critical bugs
- [ ] Documentation updated

**Estimated Time**: 4-5 hours

**Dependencies**: All integration tasks complete

---

### Phase 5 Summary

| Component | Subagent | Sequential | Total Time |
|-----------|-----------|------------|------------|
| E2E Test Suite | 10-12 hrs | - | 10-12 hrs |
| GitHub Integration | 6-8 hrs | - | 6-8 hrs |
| CI/CD Hooks | 5-6 hrs | - | 5-6 hrs |
| Notification Systems | 4-5 hrs | - | 4-5 hrs |
| Config Updates | - | 2-3 hrs | 2-3 hrs |
| Event Log Integration | - | 2-3 hrs | 2-3 hrs |
| CLI Integration | - | 2-3 hrs | 2-3 hrs |
| Testing & Validation | - | 4-5 hrs | 4-5 hrs |
| **Total** | **25-31 hrs** | **10-14 hrs** | **35-45 hrs** |

**Parallel Time**: 25-31 hrs (parallel tasks) + 10-14 hrs (sequential) = **35-45 hrs**
**Sequential Time**: 32-40 hrs (if all tasks sequential)
**Time Savings**: 3-6 hours (9-15% reduction)

---

## Overall Summary

### Total Timeline (Parallelized)

| Phase | Parallel Tasks | Sequential Tasks | Total Time |
|-------|---------------|------------------|------------|
| Phase 1: v0.3.0 (Safety & Coordination) | 10-14 hrs | 9-12 hrs | 19-26 hrs |
| Phase 2: v0.4.0 (Observability) | 11-15 hrs | 6-9 hrs | 17-24 hrs |
| Phase 3: Comprehensive Testing | - | 7-10 hrs | 7-10 hrs |
| Phase 4: v1.0.0 (Production-Ready) | 14-19 hrs | 4-6 hrs | 18-25 hrs |
| Phase 5: v1.1.0 (High-ROI Integrations) | 25-31 hrs | 10-14 hrs | 35-45 hrs |
| **Total** | **60-79 hrs** | **36-51 hrs** | **96-130 hrs** |

### Sequential Timeline (No Parallelization)

| Phase | Tasks | Total Time |
|-------|-------|------------|
| v0.3.0 (Safety & Coordination) | All sequential | 16-20 hrs |
| v0.4.0 (Observability) | All sequential | 12-16 hrs |
| v1.0.0 (Production-Ready) | All sequential | 24-28 hrs |
| v1.1.0 (High-ROI Integrations) | All sequential | 32-40 hrs |
| **Total** | - | **84-104 hrs** |

### Time Savings

**Parallelized Time**: 96-130 hours
**Sequential Time**: 84-104 hours
**Savings**: -12 to -26 hours (actually slower in some cases due to integration overhead)

**Analysis**: Parallelization shows **marginal benefits** for this implementation because:

1. **Integration Overhead**: Sequential integration tasks add significant time
2. **Coordination Complexity**: Managing multiple subagents adds overhead
3. **Testing Bottleneck**: Comprehensive testing cannot be parallelized
4. **Small Codebase**: Village modules are small, so parallel benefits are limited

**Recommendation**: **Sequential implementation** is preferred because:

- Simpler coordination (single developer or one agent)
- Less integration overhead
- Faster iteration (no waiting for subagents)
- Better code quality (single vision vs fragmented development)
- Lower complexity (no subagent management)

---

## Recommended Implementation Strategy

### Sequential Approach (Preferred)

**Phase 1: v0.3.0 (16-20 hours)**
1. Implement state_machine.py
2. Implement conflict_detection.py
3. Update config.py
4. Integrate with queue.py and resume.py
5. Testing and validation

**Phase 2: v0.4.0 (12-16 hours)**
1. Implement metrics.py
2. Implement event_query.py
3. Implement dashboard.py
4. Update config.py
5. Integrate with CLI and event_log.py
6. Testing and validation

**Phase 3: v0.3.0 + v0.4.0 Comprehensive Testing (7-10 hours)**
1. E2E workflow testing
2. Cross-version integration testing
3. Bug fixes and stabilization

**Phase 4: v1.0.0 Production-Ready (24-28 hours)**
1. Documentation updates
2. Test coverage improvement
3. Bug fixes and stabilization
4. Validation testing
5. Release checklist validation

**Phase 5: v1.1.0 High-ROI Integrations (32-40 hours)**
1. E2E test suite
2. GitHub integration
3. CI/CD hooks
4. Notification systems
5. Config and CLI integration
6. Testing and validation

**Total Sequential Time**: 84-104 hours (12-13 weeks at 8 hours/week)

---

## When to Use Parallelization

Parallelization is beneficial when:

1. **Large Codebase**: Modules are 500+ lines (not 150-300 lines)
2. **Highly Independent**: No cross-module dependencies during development
3. **Multiple Developers**: Actually have 2-3 developers available
4. **Long Development Cycles**: Modules take 2+ weeks each (not 1-2 days)

**For Village**: Sequential is preferred because:

- Small modules (150-300 lines each)
- High integration overhead (sequential integration tasks)
- Better code quality with single vision
- Faster iteration and debugging

---

## Conclusion

This PRD defines both parallelized and sequential implementation strategies for Village v0.3.0 → v1.1.0.

**Recommended Strategy**: Sequential implementation

**Rationale**:
- Lower coordination complexity
- Better code quality (single vision)
- Faster iteration and debugging
- Less integration overhead
- Similar total time (84-104 hrs sequential vs 96-130 hrs parallelized)

**Alternative Strategy**: Parallelized implementation (if multiple developers available)

**Use When**:
- Multiple developers/subagents can work in parallel
- Development cycles are long (2+ weeks per module)
- Modules are large (500+ lines each)

---

## Appendix A: Subagent Coordination Protocol

If using parallelized approach:

### Phase Start

1. **Define parallel tasks** (from this PRD)
2. **Assign subagents** (1 subagent per parallel task)
3. **Set clear interfaces** (module API, function signatures)
4. **Define completion criteria** (acceptance criteria from each task)

### Parallel Execution

1. **Subagents work independently** on assigned modules
2. **Periodic checkpoints** (daily progress updates)
3. **Code reviews** when subagents complete tasks
4. **Integration readiness** (verify interfaces match expectations)

### Sequential Integration

1. **Wait for all parallel tasks** to complete
2. **Start sequential integration tasks** (from this PRD)
3. **Integration testing** after each integration task
4. **Bug fixes** as issues discovered

### Phase Completion

1. **Comprehensive testing** (from this PRD)
2. **Documentation updates** (if needed)
3. **Phase validation** (acceptance criteria from this PRD)
4. **Proceed to next phase**

---

## Appendix B: Risk Management

### Parallelization Risks

1. **Integration Conflicts**: Modules don't integrate correctly
   - **Mitigation**: Clear interfaces defined upfront, integration testing
2. **Coordination Overhead**: Managing multiple subagents takes time
   - **Mitigation**: Clear protocols, periodic checkpoints
3. **Code Quality Fragmentation**: Different coding styles, inconsistent patterns
   - **Mitigation**: Code style enforcement (AGENTS.md), code reviews
4. **Testing Bottleneck**: Testing cannot be parallelized
   - **Mitigation**: Unit tests during development, integration testing after

### Sequential Risks

1. **Longer Timeline**: Takes more time than parallelized approach
   - **Mitigation**: Accept timeline for better code quality
2. **Single Point of Failure**: If one developer is blocked, all work stops
   - **Mitigation**: Parallel testing (can test while developing)

---

## Appendix C: Success Criteria

### Overall Success

Village implementation is successful when:

1. **v0.3.0** (Safety & Coordination)
   - [ ] State machine workflows working
   - [ ] Automatic rollback functional
   - [ ] Conflict detection operational
   - [ ] Test coverage >85% for new modules
   - [ ] Documentation updated

2. **v0.4.0** (Observability)
   - [ ] Real-time dashboard functional
   - [ ] Metrics export working
   - [ ] Event queries operational
   - [ ] Test coverage >80% for new modules
   - [ ] Documentation updated

3. **v1.0.0** (Production-Ready)
   - [ ] Audit trails comprehensive
   - [ ] Test coverage >85% overall
   - [ ] Zero critical bugs
   - [ ] Documentation complete
   - [ ] CHANGELOG.md up-to-date

4. **v1.1.0** (High-ROI Integrations)
   - [ ] E2E test suite (>30 tests) passing
   - [ ] GitHub integration working
   - [ ] CI/CD hooks working
   - [ ] Notification systems working
   - [ ] Test coverage >75% for integration modules
   - [ ] Documentation updated

### Phase Success Criteria

Each phase is successful when:

- [ ] All acceptance criteria for parallel tasks met
- [ ] All integration tasks complete and tested
- [ ] All tests passing (unit + integration)
- [ ] Documentation updated
- [ ] No critical bugs
- [ ] Phase can be marked as complete

---

**Status**: Ready for implementation
**Recommended Approach**: Sequential implementation (preferred over parallelized)
**Next Step**: Begin Phase 1 - v0.3.0 Safety & Coordination implementation
