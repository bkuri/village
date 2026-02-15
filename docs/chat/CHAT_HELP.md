# Village Chat — Slash Commands

## Knowledge-Share Commands (Available in Both Modes)
These commands work in both knowledge-share and task-create modes:

- `/help [topic]` — show help (topics: commands, tasks, context, files, policy, workflow)
- `/tasks` — list Beads tasks
- `/task <id>` — show task details
- `/ready` — show ready tasks (Beads)
- `/status` — show Village status summary
- `/queue` — alias for /ready
- `/lock` — show active locks
- `/cleanup` — show cleanup plan

## Task-Create Commands (Task-Create Mode Only)
These commands only work when in task-create mode (started with `/create` or `village chat --create`):

- `/create [title]` — enter task-create mode to define new task
- `/enable <id|all>` — mark draft(s) for batch submission
- `/edit <id>` — re-enter Q&A to modify existing draft
- `/discard <id>` — delete draft without creating task
- `/submit` — review and confirm batch submission
- `/reset` — rollback: delete created tasks, restore context
- `/drafts` — list all draft tasks with status

## Exit Commands
- `/exit` — save state and exit (with warning if pending changes)
- `/quit` — alias for /exit
- `/bye` — alias for /exit

## Workflows

### Workflow 1: Knowledge Sharing (Default Mode)
Clarify project understanding, document decisions, define goals.

```bash
$ village chat

> What are the current project goals?
> What are the technical constraints?
> /tasks
> /ready
> /exit
```

**Output**: Context files written to `.village/context/`:
- `project.md` — Project structure and overview
- `goals.md` — Current goals and objectives
- `constraints.md` — Technical constraints and limitations
- `assumptions.md` — Working assumptions
- `decisions.md` — Key decisions made
- `open-questions.md` — Outstanding questions

### Workflow 2: Task Creation (Single Task)
Define a single task for execution in Beads.

```bash
$ village chat --create

> /create "Add Redis caching"
> [Q: What is the scope?] feature
> [Q: What are success criteria?]
  - Cache API responses with 5-minute TTL
  - Reduces database load by 60%
  - Cache invalidation on updates
> [Q: Any blockers?]
  - Need Redis server provisioned
> [Q: Estimate?] 1 day
> /drafts
> /enable df-a1b2c3
> /submit
> /exit
```

**Output**: Beads task created with ID `bd-a1b2c3`

### Workflow 3: Task Creation (Batch)
Define multiple related tasks at once.

```bash
$ village chat --create

> /create "Add logging framework"
> [Q&A...]
> /create "Configure log levels"
> [Q&A...]
> /create "Add log rotation"
> [Q&A...]
> /drafts
> /enable all
> /submit
> /exit
```

**Output**: 3 Beads tasks created in a single batch

### Workflow 4: Review and Refine Tasks
Review all drafts, edit as needed, then submit.

```bash
$ village chat --create

> /create "Fix memory leak"
> [Q&A...]
> /drafts
> /edit df-a1b2c3
> [Q: Update description]
> /drafts
> /enable df-a1b2c3
> /submit
> /exit
```

### Workflow 5: Investigation-Driven Task Creation
Create investigation tasks for performance issues.

```bash
$ village chat --create

> /create "Investigate: Slow database queries"
> [Q: What scope?] investigation
> [Q: Success criteria?]
  - Identify slow queries (>500ms)
  - Propose indexing strategy
  - Benchmark before/after
> /drafts
> /enable df-a1b2c3
> /submit
> /exit
```

### Workflow 6: Reset and Rollback
If you made a mistake, reset to undo task creation.

```bash
$ village chat --create

> /create "Wrong task"
> [Q&A...]
> /submit
> [Oops, wrong title!]
> /reset
> [Tasks deleted, drafts preserved]
> /exit
```

**Note**: Reset deletes created Beads tasks but preserves all drafts for resubmission.

### Workflow 7: Automatic Task Decomposition
When tasks are complex, Village automatically offers to break them down using Sequential Thinking.

```bash
$ village chat --create

> /create "Build a new authentication system with OAuth2, MFA, and session management"
> [LLM parses task spec]
> [LLM detects complexity: "This task has multiple distinct deliverables"]
> 
> ┌────────────────────────────────────────────────────┐
> │ BREAKDOWN: Build authentication system             │
> ├────────────────────────────────────────────────────┤
> │ 1. Setup OAuth2 provider integration               │
> │    [depends: none] [effort: 4 hours]               │
> │                                                    │
> │ 2. Implement MFA with TOTP                         │
> │    [depends: Setup OAuth2] [effort: 3 hours]       │
> │                                                    │
> │ 3. Add session management with Redis               │
> │    [depends: Setup OAuth2] [effort: 2 hours]       │
> │                                                    │
> │ 4. Create authentication middleware                │
> │    [depends: MFA, Session] [effort: 2 hours]       │
> │                                                    │
> │ 5. Write integration tests                         │
> │    [depends: Middleware] [effort: 3 hours]         │
> └────────────────────────────────────────────────────┘
> 
> Actions:
>   /confirm   Create all subtasks in Beads
>   /edit      Refine entire breakdown
>   /discard   Cancel this breakdown
>
> /confirm
> ✓ Created 5 subtasks:
>   bd-a1b2: Setup OAuth2 provider integration
>   bd-c3d4: Implement MFA with TOTP
>   bd-e5f6: Add session management with Redis
>   bd-g7h8: Create authentication middleware
>   bd-i9j0: Write integration tests
> /exit
```

**How it works:**
1. After parsing your task, LLM evaluates complexity
2. If complex (multiple deliverables, phases, or parallel work possible), decomposition is offered
3. Sequential Thinking generates structured breakdown with dependencies
4. Dependencies are mapped to task titles (not indices) for clarity
5. Confirm creates all subtasks with proper blocking relationships

**Tip:** Use `/discard` to skip decomposition and create as a single task.

### Workflow 8: Mixed Mode
Start in knowledge-share mode, switch to task-create as needed.

```bash
$ village chat

> /tasks
> /ready
> What is the priority of bd-xxxxxx?
> /create "Fix authentication issue"
> [Q&A...]
> /drafts
> /exit
```

## Files

### Context Files (Knowledge-Share Mode)
Written to `.village/context/`:
- `project.md` — Project structure and overview
- `goals.md` — Current goals and objectives
- `constraints.md` — Technical constraints and limitations
- `assumptions.md` — Working assumptions
- `decisions.md` — Key decisions made
- `open-questions.md` — Outstanding questions

### Draft Files (Task-Create Mode)
Written to `.village/drafts/`:
- `df-a1b2c3.json` — Draft task (JSON format)

### Session State
Written to `.village/session.json`:
- Current mode (knowledge-share or task-create)
- Pending enable IDs
- Created task IDs (for rollback)
- Context diffs (for restoration)

## Exit Codes

For automation and scripting:

| Code | Name | Description |
|-------|-------|-------------|
| 0 | SUCCESS | Clean exit |
| 1001 | DRAFT_NOT_FOUND | Draft file not found |
| 1002 | DRAFT_NOT_FOUND_ON_ENABLE | Draft not found on /enable |
| 1003 | DRAFT_NOT_FOUND_ON_EDIT | Draft not found on /edit |
| 1004 | DRAFT_NOT_FOUND_ON_DISCARD | Draft not found on /discard |
| 2001 | NO_DRAFTS_ENABLED | No drafts enabled for /submit |
| 2002 | BATCH_SUBMISSION_FAILED | Batch creation failed |
| 2003 | INVALID_DRAFT_JSON | Draft JSON is invalid |
| 3001 | NO_CREATED_TASKS | No tasks created (for reset) |
| 3002 | RESET_FAILED | Reset operation failed |
| 4001 | MODE_CONFLICT | Command not available in current mode |
| 5001 | INVALID_STATE | Session state corrupted |
| 5002 | OPERATION_FAILED | Critical error (e.g., Beads not found) |

## Examples

### Example 1: Understanding a New Codebase
```bash
$ village chat

> What is the project structure?
> How are components organized?
> What are the key technologies?
> /tasks
> /ready
> /exit
```

### Example 2: Creating Tasks from User Story
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

### Example 3: Creating Feature, Bug, and Investigation Tasks
```bash
$ village chat --create

> /create "Feature: Add dark mode"
> [Q&A... scope: feature]
> /create "Bug: Fix memory leak in worker"
> [Q&A... scope: fix]
> /create "Investigation: Performance bottleneck"
> [Q&A... scope: investigation]
> /drafts
> /enable all
> /submit
> /exit
```

## Tips

1. **Start in knowledge-share mode** to understand the project first
2. **Use `/tasks` and `/ready`** to see what work is in progress
3. **Use `/create`** to structure your thinking about a task
4. **Use `/drafts`** to review all drafts before submitting
5. **Use `/edit`** to refine drafts after seeing them listed
6. **Use `/enable all`** to submit multiple tasks at once
7. **Use `/reset`** if you make mistakes (deletes tasks, preserves drafts)
8. **Use `/exit`** to save session state for next time
