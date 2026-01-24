# Village Chat — Workflow Examples

This document provides real-world examples of using Village Chat for different scenarios.

## Example 1: Understanding a New Codebase

**Goal**: Document architecture and identify technical debt

```bash
$ village chat

> What is the project structure?
> How are components organized?
> What are the key technologies?
> /tasks
> /ready
> /exit
```

**Output**: `.village/context/project.md` with architecture overview

**Result**: You now have documented understanding of the codebase to reference while working.

---

## Example 2: Creating Tasks from User Story

**Goal**: Convert user story into actionable tasks

```bash
$ village chat --create

> /create "User: Login with SSO"
> [Q: What success criteria?]
  - User can click "Login with SSO"
  - Redirects to IdP, authenticates, returns to app
  - Session token stored correctly
> [Q: What blockers?]
  - Need IdP configuration
  - OAuth client registration
> /create "Admin: Configure SSO provider"
> /drafts
> /enable all
> /submit
> /exit
```

**Output**: 2 Beads tasks created (bd-xxxxxx, bd-yyyyyy)

**Result**: User story broken into two implementable tasks: one for user-facing feature, one for admin configuration.

---

## Example 3: Investigation-Driven Task Creation

**Goal**: Create investigation tasks for performance issue

```bash
$ village chat --create

> /create "Investigate: Slow database queries"
> [Q: What scope?] investigation
> [Q: What success criteria?]
  - Identify slow queries (ex: >500ms)
  - Propose indexing strategy
  - Benchmark before/after
> [Q: Any blockers?]
  - Need database access for profiling
> [Q: Estimate?] 2 days
> /drafts
> /enable df-a1b2c3
> /submit
> /exit
```

**Output**: 1 investigation task in Beads

**Result**: Structured investigation task with clear success criteria and estimate.

---

## Example 4: Reviewing and Refining Tasks

**Goal**: Refine task before submitting to team

```bash
$ village chat --create

> /create "Fix: Memory leak in worker"
> [Q: What scope?] fix
> [Q: Description?]
  Worker process grows unbounded after 24h of operation
> [Q: Success criteria?]
  - No memory growth after 48h test
  - Heap profiling shows no leaks
> [Q: Estimate?] 3 days
> /drafts

# Review the draft, realize description is too vague
> /edit df-a1b2c3
> [Q: Update description?]
  Worker process grows from 50MB to 2GB over 24h.
  Suspected cause: Event emitter not cleaning up references.
  Location: src/workers/event_handler.py:142
> /drafts
> /enable df-a1b2c3
> /submit
> /exit
```

**Output**: 1 refined task with specific details

**Result**: Task is now implementable with clear scope and location hints.

---

## Example 5: Batch Workflow

**Goal**: Create multiple related tasks in one session

```bash
$ village chat --create

> /create "Add logging framework"
> [Q: What scope?] feature
> [Q: Success criteria?]
  - Structured logging with levels (debug, info, warn, error)
  - JSON format for log aggregation
  - Configurable log level
> [Q: Estimate?] 2 days

> /create "Configure log levels"
> [Q: What scope?] feature
> [Q: Success criteria?]
  - Log levels configurable via environment
  - Default: info in production, debug in development
> [Q: Estimate?] 0.5 days

> /create "Add log rotation"
> [Q: What scope?] feature
> [Q: Success criteria?]
  - Rotate logs daily
  - Retain last 7 days
  - Compress old logs
> [Q: Estimate?] 1 day

> /drafts
> /enable all
> /submit
> /exit
```

**Output**: 3 related Beads tasks created

**Result**: Logging feature broken into three implementable chunks.

---

## Example 6: Debugging with Knowledge-Share Mode

**Goal**: Understand why a test is failing

```bash
$ village chat

> What is the test coverage policy?
> What are the current test failures?
> /task bd-xxxxxx

# See the task details
> What are the dependencies for this task?
> /ready

# See what's blocking this task
> /exit
```

**Output**: Context files updated with understanding of test policy and task relationships

**Result**: You now understand why the test exists and what it's waiting for.

---

## Example 7: Reset and Rollback

**Goal**: Undo task creation if you made a mistake

```bash
$ village chat --create

> /create "Wrong task"
> [Q&A for wrong task...]

> /drafts
> /enable df-a1b2c3
> /submit

# Oops, submitted with wrong title
> /reset

Output: Deleting 1 task: bd-a1b2c3
Output: Preserving 1 draft: df-a1b2c3

> /edit df-a1b2c3
> [Q: Update title?]
  Correct task title here
> /drafts
> /enable df-a1b2c3
> /submit
> /exit
```

**Output**: Wrong task deleted, draft preserved and resubmitted

**Result**: No wasted tasks in Beads, correct task created.

---

## Example 8: Planning a Feature Release

**Goal**: Create comprehensive task list for a feature

```bash
# First, understand current state
$ village chat

> /ready
> What is blocking release v2.0?
> /tasks

# Identify gaps
> /exit

# Now create tasks for missing work
$ village chat --create

> /create "Feature: Implement API rate limiting"
> [Q&A... scope: feature, estimate: 2 days]

> /create "Docs: Add rate limiting documentation"
> [Q&A... scope: feature, estimate: 0.5 days]

> /create "Test: Add rate limiting tests"
> [Q&A... scope: feature, estimate: 1 day]

> /create "Deploy: Configure rate limits in production"
> [Q&A... scope: feature, estimate: 0.5 days]

> /drafts
> /enable all
> /submit
> /exit
```

**Output**: 4 tasks created (implementation, docs, tests, deployment)

**Result**: Comprehensive task list covering all aspects of feature delivery.

---

## Example 9: Mixed Workflow

**Goal**: Switch between knowledge-share and task-create as needed

```bash
# Start in knowledge-share mode
$ village chat

> /tasks
> /ready

# See task bd-xxxxxx needs clarification
> /task bd-xxxxxx

# Understand the task context
> /create "Fix authentication issue"
> [Q&A... scope: fix, estimate: 1 day]

> /drafts
> /enable df-a1b2c3
> /submit
> /exit
```

**Output**: New task created, linked to understanding from existing work

**Result**: Seamless workflow between understanding and action.

---

## Example 10: Discarding Unwanted Drafts

**Goal**: Clean up drafts that aren't needed

```bash
$ village chat --create

> /create "Draft idea 1"
> [Q&A...]
> /create "Draft idea 2"
> [Q&A...]
> /create "Draft idea 3"
> [Q&A...]

> /drafts
# Output shows 3 drafts

# Realize draft 2 isn't needed
> /discard df-yyyyyy
Output: Discarded draft: df-yyyyyy

> /drafts
# Now shows only 2 drafts

> /enable all
> /submit
> /exit
```

**Output**: 2 tasks created, 1 draft discarded

**Result**: Clean task list without unwanted work.

---

## Tips for Effective Workflows

1. **Start in knowledge-share mode** to understand the project first
2. **Use `/tasks` and `/ready`** to see what's in progress before creating new work
3. **Answer Q&A thoroughly** — the structure helps you think through the task
4. **Use `/drafts` often** to review what you've created
5. **Use `/edit` to refine** — drafts are meant to be iterated on
6. **Use `/discard` liberally** — it's better to not create a task than to create a vague one
7. **Use `/reset` as safety net** — mistakes are easy to undo
8. **Document decisions** in knowledge-share mode to provide context for future tasks

## Common Patterns

### Pattern 1: Epic Breakdown
```bash
# For large epics, break into stories
village chat --create

> /create "Epic: Migrate to microservices"
# Too big, break it down
> /create "Story: Extract authentication service"
> /create "Story: Extract user service"
> /create "Story: Extract order service"
> /create "Story: Set up API gateway"
> /drafts
> /enable all
> /submit
```

### Pattern 2: Bug Fix Flow
```bash
# For bug reports
village chat --create

> /create "Bug: Fix [issue]"
# Q: scope? fix
# Q: description? [error reproduction, expected vs actual]
# Q: success criteria? [tests pass, verified in staging]
# Q: blockers? [logs, reproduction steps]
> /enable df-xxxxx
> /submit
```

### Pattern 3: Tech Debt Reduction
```bash
# For addressing technical debt
village chat --create

> /create "Refactoring: Extract duplicate code"
# Q: scope? refactoring
# Q: success criteria? [tests still pass, code coverage maintained]
# Q: blockers? [tests for affected modules]
> /enable df-xxxxx
> /submit
```

### Pattern 4: Spikes/Investigations
```bash
# For uncertain work
village chat --create

> /create "Investigation: Explore technology X"
# Q: scope? investigation
# Q: success criteria? [prototype working, documented findings]
# Q: estimate? 2-3 days
> /enable df-xxxxx
> /submit
```

---

## Next Steps

1. Try **Example 1** to understand your current project
2. Try **Example 2** to create your first task
3. Try **Example 4** to practice editing drafts
4. Try **Example 7** to practice resetting
5. Combine patterns to create complex workflows
