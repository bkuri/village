# Village --- Python Rewrite PRD (Updated)

## Purpose

Village is a **CLI-native parallel development orchestrator** built on:

-   **Beads** --- task DAG and readiness
-   **tmux** --- execution runtime and observability
-   **git worktrees** --- isolation
-   **OpenCode** --- agent execution
-   **ppc** --- deterministic contract generation

Village is intentionally:

-   daemonless
-   state-light
-   text-based
-   fully inspectable
-   safe by default

------------------------------------------------------------------------

## Design Principles

1.  **No surprises**
    -   Ambiguous commands default to planning mode.
    -   Explicit commands perform actions.
2.  **Truth over intention**
    -   tmux pane IDs are the authoritative runtime handle.
3.  **One source of readiness**
    -   `bd ready` → work readiness
    -   `village ready` → execution readiness
4.  **Separation of concerns**
    -   `ready` interprets
    -   `status` reports
    -   `queue/resume` act
5.  **Everything scriptable**
    -   JSON output is first‑class API.

------------------------------------------------------------------------

## Core Concepts

### Task

-   Identified by Beads ID (`bd-xxxx`)
-   Has deps and readiness

### Worker

-   One tmux pane
-   One OpenCode instance
-   One claimed task

### Lock

-   File-backed lease
-   Stores tmux pane ID
-   ACTIVE if pane exists
-   STALE otherwise

### Orphans

-   Stale locks
-   Untracked worktrees

------------------------------------------------------------------------

## Command Surface (Final)

### Runtime lifecycle

    village up [--dry-run|--plan]
    village down

### Work execution

    village resume <id> [agent] [--detached]
    village resume [--apply]
    village queue [--n N] [agent] [--dry-run|--plan]

### Read-only inspection

    village ready [--json]
    village status [flags]

### Maintenance

    village cleanup [--dry-run|--plan]
    village unlock <id> [--force]

------------------------------------------------------------------------

## Command Semantics

### village up

Mutating. Idempotent.

Ensures: - `.village/` - `.village/config` - `.village/locks/` -
`.worktrees/` - Beads initialized - tmux session exists - dashboard
window created

Does **not** start workers.

Supports: - `--dry-run` / `--plan`

------------------------------------------------------------------------

### village down

Stops tmux session only.

------------------------------------------------------------------------

### village ready

Non-mutating.

Answers:

> "Is this environment ready to execute work?"

Reports at high level: - environment readiness - runtime readiness -
presence of orphans - work availability

Produces ordered **suggested actions**.

Supports: - `--json`

Never mutates state.

------------------------------------------------------------------------

### village status

Non-mutating.

Pure inspection.

Flags: - `--short` - `--workers` - `--locks` - `--orphans` - `--queue` -
`--json`

No recommendations by default.

------------------------------------------------------------------------

### village resume `<id>`{=html}

Explicit action.

-   Resumes specific task
-   Creates or reuses worktree
-   Creates tmux window
-   Captures pane ID
-   Writes lock
-   Starts OpenCode
-   Injects contract

Acts immediately.

------------------------------------------------------------------------

### village resume (no id)

Implicit continuation.

Default behavior: - **plan only** - prints recommended next action

With:

    village resume --apply

Executes the plan.

Decision order: 1. ensure runtime via `up` 2. attach if active workers
exist 3. cleanup if stale locks exist 4. queue ready tasks if available
5. otherwise show `ready` summary

------------------------------------------------------------------------

### village queue

Explicit scheduler.

-   consumes `bd ready`
-   skips ACTIVE locks
-   steals STALE locks
-   auto-names windows
-   uses detached mode

Supports: - `--dry-run` / `--plan`

------------------------------------------------------------------------

### village cleanup

Housekeeping command.

Default scope: - remove stale locks only

Optional future: - worktree pruning behind flags

Supports: - `--dry-run` / `--plan`

------------------------------------------------------------------------

## Lock File Schema

    id=bd-a3f8
    pane=%12
    window=build-1-bd-a3f8
    agent=build
    claimed_at=2026-01-22T10:41:12

Pane ID is the authoritative lease handle.

------------------------------------------------------------------------

## JSON Contract

All JSON output:

-   valid JSON only
-   no ANSI
-   stable keys
-   versioned schema

Top-level example:

``` json
{
  "command": "ready",
  "version": 1,
  "overall": {
    "state": "ready_with_actions",
    "reason": "stale_locks"
  },
  "suggested_actions": [
    {
      "action": "village cleanup",
      "reason": "stale_locks",
      "blocking": false
    }
  ]
}
```

------------------------------------------------------------------------

## Module Layout

    village/
      cli.py
      config.py
      probes/
        tools.py
        tmux.py
        beads.py
        repo.py
      locks.py
      worktrees.py
      queue.py
      resume.py
      cleanup.py
      ready.py
      status.py
      render/
        text.py
        json.py

------------------------------------------------------------------------

## Non‑Goals

-   background daemon
-   persistent database
-   cloud coordination
-   remote workers
-   GUI

Village remains a **local-first flow engine**.

------------------------------------------------------------------------

## Success Criteria

-   `village ready` answers "what now?"
-   `village resume` resumes both tasks and flow
-   no accidental side effects
-   predictable recovery after crashes
-   readable codebase under 2k LOC
