# Village — Comprehensive Project Critique

**Date**: 2026-04-19
**Reviewer**: AI-assisted audit
**Scope**: Architecture, code quality, documentation, testing, product identity, release readiness

---

## Executive Summary

Village is an ambitious, philosophically coherent project with a clear thesis: **coordination infrastructure for parallel AI agent development, local-first, auditable, no magic**. At ~31K lines of Python across 140+ modules, with 2,093 tests (2,059 passing), extensive documentation, and a real-world deployment history, it is genuinely impressive in scope.

However, the project suffers from **identity drift**, **documentation sprawl**, **stale references to removed systems**, and several architectural inconsistencies that would confuse a new user or contributor. The gap between what Village *is* and what Village *presents itself as* is the single biggest obstacle to a confident public release.

**Verdict**: Village is 70% of the way to a launch-worthy v1.0. The remaining 30% is primarily documentation hygiene, naming consistency, and closing a few architectural gaps — not new features.

---

## 1. Product Identity & Positioning

### The Good

- The core thesis is **sharp and defensible**: "A tiny operating system for parallel development. No daemon. No database. No hidden state." This is a real differentiator in a market of opaque agent orchestration tools.
- The philosophy of "truth over intention" (tmux pane = runtime truth) is powerful and well-articulated.
- The role-based specialist model (planner, builder, scribe, council, doctor, watcher, greeter) gives Village personality and makes it approachable.
- The spec-driven build loop with Ralph Wiggum methodology is well-integrated and well-documented.

### The Problems

#### 1.1 "Elder" → "Scribe" Rename Was Half-Completed

The CHANGELOG for v2.0.0 references `village elder` extensively:
```
- village elder see/fetch, elder ask, elder curate/upkeep, elder stats, elder monitor, elder goals
```
But the actual CLI command is `village scribe`. The code has no references to "elder" anywhere. The CHANGELOG entry is **internally inconsistent** with itself — it lists "elder" commands in a release that also says it introduced the role-based CLI architecture with `scribe` as the role name.

**Impact**: Confuses anyone reading the changelog to understand the project's evolution.

#### 1.2 The README and Quickstart Reference Two Different Task Systems

The QUICKSTART.md still references **Beads** (`bd init`, `bd ready`, `bd create`, `cargo install beads`) as the primary task management system. The README and CHANGELOG say Beads was replaced with a native task store in v2.0.0. The README's command reference correctly uses `village tasks`, but the Quickstart still tells users to install Beads via Cargo.

**Impact**: A new user following the Quickstart would be completely lost — the commands they're told to run don't exist.

#### 1.3 The man page (`village.1.md`) Is Severely Outdated

The man page references:
- `village queue`, `village dequeue`, `village resume-task`, `village cancel-task` (flat commands, not role-based)
- `village chat` (now `village greeter` or `village scribe`)
- Beads as a dependency (`beads(1)` in SEE ALSO)
- Config path `~/.config/village/config.toml` (Village uses `.village/config` INI)
- Worktree path `.village/worker-trees/` (now `.worktrees/`)

**Impact**: Anyone reading the man page gets incorrect information about every aspect of the tool.

#### 1.4 PKGBUILD Has Wrong Version

The PKGBUILD hardcodes `pkgver=1.0.0`, but the CHANGELOG shows the current release as 2.0.0. The build system uses `hatch-vcs` for dynamic versioning, but the PKGBUILD doesn't account for this.

#### 1.5 The Roadmap Is Internally Contradictory

The ROADMAP.md has:
- A header saying "Current Status: v1.0.0"
- Sections marked ✅ for v0.2.3, v0.3.0, v0.4.0 — but these appear *twice* (duplicated content)
- Sections for v0.3.0 and v0.4.0 with `[ ]` unchecked items alongside `[x]` checked items for the same phases
- A table showing v0.3.0 and v0.4.0 as "📅 Planned" while the detailed sections say ✅ Complete

---

## 2. Documentation Audit

### 2.1 Documentation Sprawl

The project has **16,241 lines of markdown** in `docs/` alone (plus README, AGENTS.md, CHANGELOG, CONTRIBUTING, etc.). This is a **lot** for a project that prides itself on simplicity. The documentation structure is:

| Document | Lines | Status |
|----------|-------|--------|
| README.md | 600+ | Good, comprehensive |
| AGENTS.md | 600+ | Good but duplicates README |
| docs/PRD.md | ~500 | Contains outdated references |
| docs/ROADMAP.md | ~800+ | Internally contradictory |
| docs/QUICKSTART.md | ~600+ | **Critically outdated** (references Beads) |
| docs/EXTENSIBILITY.md | ~200 | Good |
| docs/EXTENSIBILITY_GUIDE.md | ~300 | Good |
| docs/EXTENSIBILITY_API.md | ~300 | Good |
| docs/ACP_*.md | ~500+ | Good |
| docs/archive/ | ~465 | Archive, fine |
| docs/chat/ | ~6 files | Mix of current and stale |
| docs/templates/ | 3 files | Reference Beads |
| docs/examples/ | 9 files | Reference Beads |
| docs/PROPOSALS.md | ~500+ | References Beads |
| docs/SHELL_COMPLETION.md | Unknown | Likely fine |

**Recommendation**: Audit every `.md` file for Beads references and update them. The quickstart is the most critical fix.

### 2.2 AGENTS.md vs README.md Duplication

The top-level AGENTS.md and README.md have significant overlap — both contain:
- Full command reference tables
- Configuration sections
- Architecture descriptions
- Quickstart instructions

AGENTS.md is meant for AI agents contributing to Village itself, while README.md is for users. But the overlap means updates must be synchronized manually. The AGENTS.md in this repo is 24KB — it should be leaner and reference the README for user-facing content rather than duplicating it.

### 2.3 Missing VOICE.md

The AGENTS.md references VOICE.md as the distilled project knowledge for agents, but it doesn't exist. This means the scribe's curate workflow hasn't been run, and a key piece of the self-improving documentation story is missing.

---

## 3. Code Quality

### 3.1 Architecture

The codebase is well-structured:
- Clean module boundaries (`village/scm/`, `village/cli/`, `village/chat/`, `village/extensibility/`)
- Proper use of Protocol for SCM abstraction
- Clear error hierarchy with exit codes
- Good separation of concerns (roles, transports, dispatch)

### 3.2 Code Style

- Ruff passes cleanly — no lint issues
- Consistent use of `pathlib.Path` throughout
- Type hints present and `mypy --strict` configured
- Clean import organization

### 3.3 Notable Issues

#### Dead/Stale References
While `village/` source code has no `beads` references (clean), the `docs/` and `README` still point to Beads as if it's a required dependency. The only source-code references to `bd` are two minor comments in `lifecycle.py` and `drafts.py`.

#### Overly Large Files
Several modules exceed 500 lines:
- `village/chat/llm_chat.py` (600 lines)
- `village/chat/subcommands.py` (594 lines)
- `village/cli/work.py` (582 lines)
- `village/cli/watcher.py` (558 lines)
- `village/resume.py` (567 lines)
- `village/queue.py` (484 lines)
- `village/notifications.py` (463 lines)
- `village/state_machine.py` (462 lines)

These aren't necessarily problems, but they suggest some modules could benefit from further decomposition — especially `resume.py` which handles window creation, lock management, contract injection, and rollback all in one file.

#### Notifications Module (463 lines) With No Tests Using It
The notifications module is substantial but appears to be a v1.1 roadmap feature that's been partially implemented. Verify whether this is actually wired into any CLI commands or if it's speculative code.

#### The `opencode.py` Module Is 9 Lines
```python
"""OpenCode integration module."""
```
This is essentially empty. Either implement it or remove it and reference OpenCode directly where needed.

---

## 4. Testing

### 4.1 Test Suite Health

| Metric | Value |
|--------|-------|
| Total tests | 2,093 |
| Passing | 2,059 |
| Failing | 1 |
| Skipped | 33 |
| Test LOC | 35,436 (more than source code!) |
| Runtime | ~23 seconds |

This is a **strong** test suite. Having more test code than production code (35K vs 31K) shows commitment to correctness.

### 4.2 The One Failure

```
TestResumeWithRollback::test_resume_failure_with_rollback
AssertionError: assert True is False
```

This test expects `execute_resume()` to fail (returning `success=False`) when the worktree can't be properly set up, but it's succeeding. The test creates a standalone git repo in the worktree path and mocks `reset_workspace`, but `execute_resume()` is actually succeeding because it manages to complete all phases (worktree exists, tmux window creation succeeds in the test environment, lock is written, contract is generated).

**Root cause**: The test doesn't mock enough of the execution path to actually trigger a failure. It needs to either:
- Mock `_create_resume_window` to return `None` (simulating window creation failure)
- Mock a deeper failure in the OpenCode execution path
- Or restructure the test to use a real failure scenario

**Fix difficulty**: Easy — this is a test bug, not a production bug.

### 4.3 Skipped Tests

- **19 tests** skipped because `JJ backend not implemented yet (planned for v2)` — reasonable
- **12 tests** skipped with `beads_client removed - needs rewrite for task store` — **should be fixed or removed**
- **1 test** skipped with `Ollama not available in CI` — reasonable
- **1 test** skipped with `Requires tmux + agent binary (not available on CI)` — the same class as the failing test

**Recommendation**: The 12 `beads_client` skipped tests are dead weight. Either rewrite them for the native task store or delete them. They represent a migration debt from the v2.0.0 Beads removal.

### 4.4 Test Quality Assessment

**Strengths**:
- Good use of `tmp_path` fixtures for filesystem isolation
- Proper mocking patterns for tmux, subprocess, and config
- Test coverage for error paths and edge cases
- Separate test files per module

**Concerns**:
- Some tests test mocks rather than behavior (e.g., the rollback test above mocks `reset_workspace` but never triggers a real failure)
- The `test_resume_rollback.py` tests are marked as CI-skipped, meaning they only run locally — risky for a CI-dependent project
- The test-to-code ratio (35K/31K) is excellent but verify that the tests are testing *meaningful behavior*, not just that mocks return what they're configured to return

### 4.5 Test Coverage

The CHANGELOG mentions coverage targets of >85% overall and >90% for critical modules. Coverage data in `.coverage` exists but is from January. Run a fresh coverage report before release.

---

## 5. What Would I Change?

### Priority 1: Documentation Hygiene (Release Blocker)

These issues would confuse or mislead anyone trying to use Village for the first time:

1. **Rewrite QUICKSTART.md** — Remove all Beads references. Use `village tasks` commands throughout. This is the #1 user-facing doc.
2. **Update village.1.md** — Completely rewrite to reflect the current CLI surface (role-based commands, native task store).
3. **Update PKGBUILD** — Sync version, fix the build to use hatch-vcs properly.
4. **Clean ROADMAP.md** — Remove duplicated sections, resolve contradictions, update the status header.
5. **Audit docs/ for Beads references** — `grep -ri "beads\|bd " docs/` and update every hit.
6. **Clean CHANGELOG.md v2.0.0 entry** — Replace "elder" references with "scribe".

### Priority 2: Code Hygiene (Should Fix Before Release)

1. **Fix the failing test** — `test_resume_failure_with_rollback` needs proper failure simulation.
2. **Remove or rewrite 12 skipped beads_client tests** — Dead test code is technical debt.
3. **Remove or implement `village/opencode.py`** — 9-line stub adds no value.
4. **Verify `village/notifications.py` is wired in** — If not wired to any CLI command, document it as v1.1 infrastructure.
5. **Generate VOICE.md** — Run `village scribe curate` to bootstrap the self-improving documentation.

### Priority 3: Product Clarity (Strongly Recommended)

1. **Clarify the "elder" vs "scribe" naming** — Pick one, update all references. The changelog says "elder", the code says "scribe". This is confusing for contributors.
2. **Reduce AGENTS.md duplication** — AGENTS.md should reference README.md for user-facing content, not duplicate it. Keep AGENTS.md focused on contributor workflow.
3. **Consolidate documentation** — 16K lines of docs is excessive. Consider whether some docs (proposals, chat PRDs, fabric patterns) should be archived or merged.
4. **Create a clear "Getting Started" path** — The Quickstart references three "paths" but Path A (brand new project) is the one that should Just Work. Make it frictionless.

### Priority 4: Architectural Improvements (Post-Release)

1. **Decompose `resume.py`** — Split into `resume_planner.py`, `resume_executor.py`, and `resume_rollback.py`. The current 567-line file does too much.
2. **Add integration tests for the build loop** — The spec-driven build loop (`village/loop.py`) is 440 lines of core logic with only unit tests. An E2E test that creates a spec and runs the loop (even with a mock agent) would catch integration bugs.
3. **Wire notifications to event system** — The notifications module exists but doesn't appear to be connected to any event hooks. Make it actually work or document it as a stub.
4. **Consider removing `docs/chat/`** — These appear to be design documents from earlier iterations. If they're not actively maintained, they'll confuse contributors.
5. **Add a `village --version` check** — Ensure `__version__` is correctly populated from hatch-vcs in all environments.

---

## 6. The Vision: What Would Make Village the Ultimate Solution

### What Village Already Does Well

1. **Philosophical coherence** — The "tiny OS for parallel development" metaphor works. The principles (no daemon, no database, no hidden state) are genuinely differentiating.
2. **Technical depth** — State machines, rollback, conflict detection, event logging, observability — this is real infrastructure, not a thin wrapper.
3. **Extensibility** — The 7 extension points are well-designed and well-documented.
4. **Role-based UX** — Planner → Builder → Watcher is a natural workflow. The routing system (ROUTE/ADVISE) is clever.
5. **Test investment** — 2,093 tests is serious. The project clearly values correctness.

### What's Missing for "Ultimate" Status

#### 6.1 A Killer Demo / Tutorial

Village needs a **5-minute wow demo**. Something like:

```bash
# Zero to running in 5 minutes
pip install village
mkdir my-project && cd my-project && git init
village up
village tasks create "Add README with project description"
village tasks create "Add .gitignore for Python" --depends-on <id-1>
village tasks create "Add hello.py with CLI" --depends-on <id-1>
village builder run
```

This demo should work on a fresh machine with zero configuration. Currently, the quickstart assumes tmux, git worktrees, and an understanding of specs.

#### 6.2 The Spec Workflow Needs To Be Accessible

Specs are Village's core concept, but creating one requires understanding the spec format, the promise signal, and the build loop. Consider:

- `village planner design "Add auth"` → auto-generates a spec from natural language
- `village builder run --demo` → runs a guided demo that creates and implements a trivial spec

#### 6.3 Visual Output

The dashboard exists (`village watcher dashboard`) but the README doesn't show what it looks like. A screenshot or ASCII art mockup in the README would help users visualize what they're getting.

#### 6.4 A Comparison Page

The PRD has an excellent "Village vs OpenCode + PPC" section. Surface this in the README. Help users understand *why* they need Village:

| Without Village | With Village |
|-----------------|-------------|
| `opencode` in 3 terminals | `village builder run -p 3` |
| Manual conflict avoidance | Automatic lock + conflict detection |
| Guess what's running | `village watcher status` |
| Lost work on crash | Event log + rollback |

#### 6.5 Plugin Discovery

The extensibility framework is excellent but there's no way to discover community extensions. Even a simple registry file or `village extensions list` command would help.

#### 6.6 Release Notes That Tell a Story

The CHANGELOG is comprehensive but reads like a commit log. For a major release (v1.0.0 or v2.0.0), write release notes that tell the story of *why* and *what changed*, not just *what was added*. The v2.0.0 entry is the most important — it removed Beads, added the role-based CLI, and fundamentally changed the product. It deserves a blog post, not just bullet points.

---

## 7. Release Readiness Checklist

Before the fanfare release, every item on this list should be ✅:

### Critical (Release Blockers)
- [ ] QUICKSTART.md rewritten without Beads references
- [ ] `village.1.md` man page updated to current CLI surface
- [ ] ROADMAP.md contradictions resolved
- [ ] Failing test fixed (`test_resume_failure_with_rollback`)
- [ ] 12 skipped beads_client tests removed or rewritten
- [ ] PKGBUILD version corrected
- [ ] CHANGELOG.md "elder" references updated to "scribe"
- [ ] Fresh test coverage report generated and >85%

### High Priority (Strongly Recommended)
- [ ] All docs/ files audited for Beads references
- [ ] AGENTS.md deduplicated against README.md
- [ ] `village/opencode.py` stub removed or implemented
- [ ] VOICE.md generated via `village scribe curate`
- [ ] CI pipeline runs full test suite (including currently-CI-skipped tests where possible)
- [ ] Release blog post or narrative CHANGELOG entry for v2.0.0

### Nice To Have (Post-Release)
- [ ] 5-minute demo walkthrough added to README
- [ ] Dashboard screenshot/ASCII art in README
- [ ] "Village vs manual" comparison table in README
- [ ] `resume.py` decomposed into smaller modules
- [ ] E2E integration test for the build loop
- [ ] `docs/chat/` design docs archived or removed
- [ ] `village/notifications.py` wired to CLI or documented as stub

---

## 8. Final Thoughts

Village is a **genuinely interesting project** with a clear point of view. In a world of AI agent tools that are either too simple (single agent wrappers) or too complex (Kubernetes for agents), Village occupies a thoughtful middle ground: **local, auditable, file-based coordination that respects existing tools**.

The core code is solid, the test suite is serious, and the architecture is well-considered. The main thing standing between the current state and a confident public release is **presentation hygiene** — making sure the documentation, examples, and onboarding materials accurately reflect what Village actually is today, not what it was six months ago.

The fact that the project has been worked on for months and has 2,093 tests shows real commitment. The release deserves to be clean. Fix the documentation, close the gaps, and ship it with confidence.

---

*"Village is intentionally boring. It does not hide execution. It does not predict intent. It does not require belief. It simply coordinates reality."*

That's a mission statement worth releasing for.
