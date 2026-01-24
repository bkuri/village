# Village v2 PRD — Workspace-Native Parallelism

## Purpose

Village v2 expands the framework without compromising its core principles.

The focus is **workspace-native execution** and **long-running resilience**.

---

## Core Goals

- native jj backend
- stronger reconciliation
- optional resource-aware scheduling
- extensibility without daemons

---

## Major Features

### 1. Jujutsu (jj) SCM Backend

- implemented via existing SCM abstraction
- workspace == jj workspace
- task == jj change
- abandon == native operation

No migration required.
Git backend remains supported.

---

### 2. Reconciliation Engine

New command:

```bash
village reconcile [--plan|--apply]
```

Detects and repairs inconsistencies between:

- tmux panes
- lock files
- workspaces
- beads tasks

Outputs planned actions before execution.

---

### 3. Resource-Aware Queueing

Optional scheduling constraints:

- `--max-workers`
- `--max-load`
- `--max-mem`

Implemented as pre-flight checks only.

Village does not manage resources — it respects them.

---

### 4. Hooks System

Optional executable hooks:

```
.village/hooks/
  on-claim
  on-release
  on-fail
```

Invoked with structured JSON payloads.

Enables:

- notifications
- custom logging
- PR automation
- metrics export

---

### 5. Contract Caching

Deterministic prompt contracts cached at:

```
.village/contracts/<task>/<agent>.md
```

Prevents unnecessary LLM regeneration.

---

## Explicit Non-Goals

- daemon mode
- distributed workers
- central coordination server
- YAML workflows
- plugin marketplaces

---

## Philosophy Reminder

Village remains:

- local-first
- file-based
- tmux-truth-driven
- human-debuggable

v2 adds power — not magic.

---

Status: **Draft / Parking Lot**
