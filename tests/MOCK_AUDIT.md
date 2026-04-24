# Mock-Overfit Audit Report

**Date**: 2026-04-18
**Auditor**: village-sfv bead
**Scope**: All `tests/` files (104 test files, ~55,700 lines total)
**Trigger**: Post-cleanup audit following vg2, sax, boz, afq bead work

---

## Executive Summary

| Severity | Files | % of Total | Description |
|----------|-------|-----------|-------------|
| **Clean** | 78 | 75% | No mock-overfit issues |
| **Minor** | 15 | 14% | Acceptable mock coupling (external deps, CLI prompts) |
| **Moderate** | 8 | 8% | Tests call wiring / implementation details |
| **Severe** | 3 | 3% | Deep mock chains, testing mocks not behavior |

**Key findings:**
- 85% of the test suite is clean or acceptably mocked
- The worst offenders are `test_runtime.py` (92 mock references, 25 assert_called), `test_dashboard.py` (ANSI escape code assertions), and `extensibility/test_registry.py` (8 tests verifying log messages)
- Many "moderate" files mock internal collaborators but verify observable behavior (return values, side effects), not just call counts
- Dataclass init tests exist in several files but are low-impact
- No identity function tests were found

---

## Severity: Severe

### `tests/test_runtime.py` (92 mock refs, 25 assert_called)

**Issues:**
- Every `test_execute_initialization_*` variant (lines 340–646) mocks 4–6 internal functions (`_ensure_directories`, `_ensure_session`, `_ensure_tasks_initialized`, `_create_dashboard`) and asserts each was called with specific arguments
- These tests are pure wiring tests: "when plan says X is needed, does execute_initialization call _ensure_X?" — renaming any private function breaks the test
- `test_ensure_directories_create_success` (line 114) and `test_ensure_tasks_initialized_success` (line 161) mock `get_config` + `get_task_store` then assert `config_mock.ensure_exists.assert_called_once()` — mocking the collaborator that's being tested
- Tests like `test_shutdown_runtime_success` (line 649) mock `kill_session` and `session_exists` then assert both were called — this tests the control flow, not the behavior

**Boundary mock exceptions (acceptable):**
- `mock_session_exists` and `mock_create_session` are tmux boundary mocks — OK
- `get_config` and `get_task_store` are service-locator mocks — borderline but common pattern

**Recommendation:** Rewrite the 7 `test_execute_initialization_*` tests as a single parameterized test that verifies the *observable result* (True/False, event log entries) rather than which internal functions were called. The `_ensure_*` private functions should be tested individually (which they already are). Estimated effort: 1–2 hours.

### `tests/test_dashboard.py` (22 mock refs, 9 assert_called)

**Issues:**
- `test_clear_screen` (line 63), `test_hide_cursor` (line 72), `test_show_cursor` (line 81), `test_move_cursor` (line 90) each mock `sys.stdout.write` and `sys.stdout.flush`, then assert exact ANSI escape sequences were written:
  ```
  mock_write.assert_called_once_with("\033[2J\033[H")
  ```
  These are testing that the implementation uses a specific escape sequence, not that the screen clears.

**Boundary mock exceptions (acceptable):**
- `test_dashboard_wait_for_input_*` and `test_dashboard_handle_input_*` mock `select.select` and `sys.stdin` — these are I/O boundary mocks, acceptable

**Recommendation:** These 4 tests should verify behavior (e.g., write was called at all, or use a captured output pattern). The ANSI sequence tests are fragile if the terminal library changes. Low priority — estimated effort: 30 min.

### `tests/extensibility/test_registry.py` (19 mock refs, 8 assert_called)

**Issues:**
- `TestExtensionRegistryLogging` class (lines 514–626) contains 8 tests that each patch `logger` and verify `mock_logger.debug.assert_called_once()` with a specific message string. These test that registration methods call `logger.debug()` — pure wiring.
- Tests verify exact message content like `"Registered processor MockChatProcessor"` — coupling to log message format.

**Acceptable patterns:**
- The rest of the file (registration, reset, getter tests) uses hand-written mock implementations (MockChatProcessor, etc.) rather than MagicMock, which is the right approach

**Recommendation:** Delete `TestExtensionRegistryLogging` entirely. Logging is a side effect that adds no behavioral guarantees. If logging is important, test it once at the integration level. Estimated effort: 15 min.

---

## Severity: Moderate

### `tests/test_resume.py` (47 mock refs, 0 assert_called)

**Issues:**
- `TestExecuteResume` (lines 304–368) mocks 3–5 internal functions (`_ensure_worktree_exists`, `_create_resume_window`, `write_lock`, `_inject_contract`, `generate_contract`) to test the execute_resume orchestration
- `TestResumeEventLogging` (lines 651–743) wraps the same mocks around execute_resume and then reads the event log — these are better because they verify observable state (events.log) rather than call counts
- `TestInjectContract` (lines 526–600) mocks `send_keys` and asserts `mock_send.call_count == 2` — this tests that _inject_contract sends exactly 2 tmux commands, which is implementation coupling

**Boundary mock exceptions (acceptable):**
- `_ensure_worktree_exists` wraps git/tmux operations — OK to mock
- `send_keys` is a tmux boundary — OK to mock
- `assess_readiness` in `TestPlanResume` is an internal collaborator, but tests verify the returned ResumeAction (observable behavior), not the mock

**Recommendation:** The event logging tests are good. The `TestInjectContract.call_count == 2` assertion is fragile — consider verifying the final state instead. Low priority — estimated effort: 30 min.

### `tests/test_resume_rollback.py` (14 mock refs, 1 assert_called)

**Issues:**
- `test_resume_failure_with_rollback` (line 52) mocks `_create_resume_window`, `_inject_contract`, and `GitSCM.reset_workspace`, then asserts `mock_reset.assert_called_once_with(worktree_path)` — this tests that rollback is triggered, which IS the behavior being tested, so it's borderline acceptable
- Other tests in this file verify `result.success` and state machine state, which is good

**Recommendation:** The `assert_called_once_with(worktree_path)` is acceptable here because verifying rollback happened IS the test purpose. No action needed.

### `tests/test_chat/test_brainstorm_workflows.py` (41 mock refs, 3 assert_called)

**Issues:**
- Every test mocks 6–7 internal brainstorm collaborators: `collect_baseline`, `generate_task_breakdown`, `create_draft_tasks`, `get_task_store`, `validate_dependencies`, `extract_task_specs`
- `test_brainstorm_creates_draft_tasks` (line 234) asserts `mock_generate.assert_called_once()` and `mock_create.assert_called_once()` — call wiring tests
- `test_brainstorm_with_existing_beads_tasks` (line 283) asserts `mock_generate.assert_called_once()` then inspects `call_args[0]` — verifying internal dispatch

**Acceptable patterns:**
- Error handling tests (`TestBrainstormErrorHandling`) verify the resulting state (error messages, session_snapshot), not mock calls
- Tests verify `state.session_snapshot` and `state.pending_enables` — observable state

**Recommendation:** The 2 assert_called tests are minor. The error handling tests are well-structured. Low priority — estimated effort: 30 min to remove the assert_called lines and rely on state assertions.

### `tests/test_e2e.py` (44 mock refs, 0 assert_called)

**Issues:**
- Heavy use of `patch("village.probes.tmux.panes")` and `patch("village.resume._create_resume_window")` + `patch("village.resume._inject_contract")` — but these are all boundary mocks (tmux, filesystem, subprocess)
- `mock_get_config` fixture patches 5 different modules' `get_config` — this is a service-locator pattern, not overfit
- Tests verify observable behavior: lock files exist, event logs contain entries, worker lists are correct

**Acceptable:** All mocks in this file are boundary mocks (tmux panes, git, resume window creation). The tests verify end-to-end behavior through file I/O and state assertions. **No action needed.**

### `tests/test_scaffold.py` (78 mock refs, 7 assert_called)

**Issues:**
- `test_new_command_without_name_prompts` (line 396) asserts `mock_exec.assert_called_once_with(...)` with exact kwargs — CLI dispatch wiring
- `test_new_command_with_name_skips_prompt` (line 422) asserts `mock_workflow.assert_not_called()` — verifies control flow
- Other assert_called tests follow the same pattern

**Acceptable patterns:**
- `test_is_inside_git_repo_*` mock `subprocess.run` — external dependency, OK
- Most tests verify `result.success`, `result.created`, file existence — observable behavior
- CLI tests use CliRunner, which is the right approach

**Recommendation:** The CLI dispatch tests (`test_new_command_*`) are borderline — they verify that the CLI routes to execute_scaffold with the right args. This is acceptable for CLI integration tests. Low priority.

### `tests/test_ci.py` (38 mock refs, 2 assert_called)

**Issues:**
- `TestTriggerBuild` tests mock `_trigger_github_actions` etc. and assert `mock_trigger.assert_called_once()` — but these verify the dispatcher calls the right platform handler, which IS the behavior
- `TestTriggerGitHubActions` etc. mock `subprocess.run` — external dependency, OK

**Acceptable:** Most mocks are subprocess boundary mocks. The trigger_build dispatch tests verify correct routing. **No action needed.**

### `tests/test_github.py` (34 mock refs, 6 assert_called)

**Issues:**
- `TestRunGhCommand` (line 47) mocks `run_command` and asserts `mock_run.assert_called_once()` — call wiring
- `TestAddPRLabels` (line 467) mocks `_run_gh_command` and asserts `assert_called_once_with(["pr", "edit", "123", "--add-label", "bugfix,enhancement"])` — tests argument formatting
- `test_creates_pr_successfully` (line 500) mocks `_run_gh_command` and `add_pr_labels` then asserts both — verifies call wiring

**Acceptable patterns:**
- `TestParseFileChanges` (line 114) has no mocks — pure function tests, good
- `TestGenerateSummary`, `TestGenerateChangesSummary` etc. — no mocks, good
- Dataclass init tests (`TestPRDescription`, `TestSyncResult`, `TestGitHubError`) are low-value but harmless

**Recommendation:** The `TestAddPRLabels` tests that verify exact gh command arguments are testing implementation details (CLI arg formatting). Consider testing at a higher level. Low priority — estimated effort: 30 min.

---

## Severity: Minor

### `tests/test_prompt.py` (6 mock refs, 2 assert_called)

Mock of `click.prompt` and `click.confirm` for fallback paths. These are boundary mocks (user input). The `assert_called_once_with` on line 103 verifies the exact click API signature, which is acceptable for testing the fallback path.

**No action needed.**

### `tests/test_dispatch.py` (34 mock refs, 1 assert_called)

Mocks `get_task_store` to provide test data. The single `assert_called_once()` is on `mock_store.list_tasks` — verifying that the dispatch handler queries the task store, which is the behavior being tested. Rest of file tests pure functions (`parse_command`, `spawn_command`).

**No action needed.**

### `tests/test_role_chat_integration.py` (36 mock refs, 0 assert_called)

All mocks are `click.prompt` patches to simulate user input — standard CLI testing pattern. Tests verify output via `capsys.readouterr()`, which tests behavior.

**No action needed.**

### `tests/test_conflicts.py` (16 mock refs, 3 assert_called)

Mocks `run_command_output_cwd` (subprocess boundary) and `_get_git_modified_files` (internal). The 3 `assert_called_once()` calls verify that `get_modified_files` dispatches to the right VCS backend, which is the function's purpose.

**No action needed.**

### `tests/test_worktrees.py` (5 mock refs, 3 assert_called)

Mocks `get_config`, `get_scm` (service locator), and `generate_window_name`. The `assert_called_once_with` on SCM methods verify the worktree creation calls the SCM with correct paths — acceptable for an integration test.

**No action needed.**

### `tests/scm/test_protocol.py` (2 mock refs, 2 assert_called)

Uses `Mock(spec=SCM)` to test protocol compliance. The `assert_called_once_with` on `mock_scm.ensure_workspace` verifies the protocol interface contract. This is testing the protocol definition, which is the file's purpose.

**No action needed.**

### `tests/test_transports/test_telegram_state.py` (11 mock refs, 5 assert_called)

Mocks Telegram Bot API (external dependency). Tests verify state machine behavior (counter, milestones, phase transitions). The `assert_called_once()` on `bot.edit_message_text` verifies the bot was notified — acceptable for a transport integration test.

**No action needed.**

### `tests/test_transports/test_telegram_transport.py` (30 mock refs, 4 assert_called)

Mocks Telegram Bot/ApplicationBuilder (external dependency). Tests verify message routing and response generation.

**No action needed.**

### `tests/test_transports/test_cli_transport.py` (5 mock refs, 3 assert_called)

Mocks `click.prompt` (user input boundary) and `run_role_chat` (collaborator). The `assert_called_once_with("builder", context=...)` verifies CLI dispatch — acceptable.

**No action needed.**

### `tests/test_chat/test_initialization.py` (13 mock refs, 2 assert_called)

Mocks `get_task_store` (service locator). Tests verify initialization behavior through return values and exceptions.

**No action needed.**

### `tests/test_scribe_research.py` (8 mock refs, 1 assert_called)

Uses `MagicMock(spec=Curator)` to test research orchestrator. The single `assert_called_once()` verifies the curator was consulted. Tests verify output content.

**No action needed.**

### `tests/test_lock_spec.py` (2 mock refs, 0 assert_called)

Mocks `get_config` (service locator). Tests verify lock behavior through file I/O.

**No action needed.**

### `tests/test_trace.py` (6 mock refs, 0 assert_called)

Mocks `get_config` (service locator). Tests verify trace formatting behavior.

**No action needed.**

### `tests/probes/test_tasks.py` (6 mock refs, 0 assert_called)

Mocks `get_task_store` (service locator). Tests verify probe output format.

**No action needed.**

### `tests/probes/test_tmux.py` (8 mock refs, 0 assert_called)

Mocks `run_command_output` (subprocess boundary). Tests verify tmux output parsing.

**No action needed.**

---

## Dataclass Init Tests

The following files contain tests that construct a dataclass and assert fields match constructor arguments. These are low-value (they test Python's dataclass machinery, not application logic) but low-risk (they won't break unless the dataclass is removed):

| File | Lines | Dataclass |
|------|-------|-----------|
| `test_resume.py` | 56–68, 74–87 | `ResumeAction`, `ResumeResult` |
| `test_conflicts.py` | 40–51, 57–66 | `WorkerInfo`, `Conflict` |
| `test_ci.py` | 42–53, 67–78, 93–101 | `CIPlatformConfig`, `BuildResult`, `BuildStatus` |
| `test_github.py` | 559–573, 585–595 | `PRDescription`, `SyncResult` |
| `test_worktrees.py` | 310–321 | `WorktreeInfo` |
| `scm/test_protocol.py` | 39–49 | `WorkspaceInfo` |
| `test_dashboard.py` | 281–291 | `DashboardState` |

**Recommendation:** Delete these tests if the dataclasses are simple (no validation logic). Keep them if the dataclass has custom `__post_init__` or validation. Estimated effort: 30 min total.

---

## Identity Function Tests

**None found.** No tests match the pattern of verifying that a default/no-op processor returns input unchanged.

---

## Implementation Coupling

Files where renaming an internal function would break tests even though behavior wouldn't change:

| File | Coupled Internal Names | Risk |
|------|------------------------|------|
| `test_runtime.py` | `_ensure_directories`, `_ensure_session`, `_ensure_tasks_initialized`, `_create_dashboard` | High |
| `test_resume.py` | `_create_resume_window`, `_inject_contract`, `_ensure_worktree_exists` | Medium |
| `test_resume_rollback.py` | `_create_resume_window`, `_inject_contract` | Low |
| `test_e2e.py` | `_create_resume_window`, `_inject_contract`, `write_lock` | Low |
| `test_dashboard.py` | `clear_screen`, `hide_cursor`, `show_cursor`, `move_cursor` | Low |
| `extensibility/test_registry.py` | (logging tests only) | Low |

---

## Recommendations Summary

### Priority 1 (Should Fix)
1. **`tests/test_runtime.py`**: Consolidate 7 `test_execute_initialization_*` tests into a parameterized test verifying observable results, not internal call wiring. ~1–2 hours.
2. **`tests/extensibility/test_registry.py`**: Delete `TestExtensionRegistryLogging` (8 tests). ~15 min.

### Priority 2 (Nice to Have)
3. **`tests/test_dashboard.py`**: Soften ANSI escape sequence assertions to verify write-was-called rather than exact bytes. ~30 min.
4. **`tests/test_chat/test_brainstorm_workflows.py`**: Remove 2 `assert_called_once()` lines, rely on state assertions. ~30 min.
5. **Dataclass init tests**: Delete trivial dataclass construction tests across 7 files. ~30 min.

### No Action Needed
- `test_e2e.py`, `test_ci.py`, `test_scaffold.py` — all mocks are boundary mocks or verify observable behavior
- `test_prompt.py`, `test_dispatch.py`, `test_role_chat_integration.py` — CLI input mocks are standard
- All transport tests — external dependency mocks are appropriate
- All probe tests — subprocess boundary mocks are appropriate
- `test_conflicts.py`, `test_worktrees.py`, `scm/test_protocol.py` — SCM boundary mocks are appropriate

---

## Total Estimated Effort

| Priority | Items | Time |
|----------|-------|------|
| Priority 1 | 2 | ~1.5 hours |
| Priority 2 | 3 | ~1.5 hours |
| **Total** | **5** | **~3 hours** |
