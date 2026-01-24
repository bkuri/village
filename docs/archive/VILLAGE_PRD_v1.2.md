# Village v1.2 PRD — Reliability & Observability

## Purpose

Village v1.2 focuses on **operational trust**.

No new orchestration concepts are introduced.
Instead, this release strengthens:

- predictability
- debuggability
- automation safety

Village should feel reliable even under heavy concurrency and frequent crashes.

---

## Design Goals

- Zero behavioral surprises
- Scriptable outputs
- Better crash forensics
- Stronger deduplication guarantees

---

## Additions

### 1. Stable Exit Codes

All commands must return meaningful exit codes.

| Code | Meaning |
|------|--------|
| 0 | success |
| 1 | generic error |
| 2 | environment not ready |
| 3 | blocked (no ready work) |
| 4 | partial success |

Enables shell scripting and automation without parsing text.

---

### 2. JSON Output Standardization

All JSON outputs must include:

```json
{
  "command": "ready",
  "version": 1,
  "status": "..."
}
```

Commands supporting JSON:

- `ready`
- `status`
- `queue --plan`
- `cleanup --plan`
- `resume` (planner mode)

---

### 3. Event Log (NDJSON)

Append-only event log:

```
.village/events.log
```

Each action appends one JSON line:

```json
{"ts":"2026-01-22T10:41:12","cmd":"queue","task":"bd-a3f8","pane":"%12","result":"ok"}
```

Uses:

- crash recovery inspection
- deduplication
- debugging
- future metrics

No indexing.
No database.
No rotation required.

---

### 4. Queue Deduplication Guard

Queue must avoid re-running tasks that were recently started.

Mechanism:

- consult events.log
- skip tasks started within configurable TTL (default: 5 min)

Override via:

```bash
village queue --force
```

---

### 5. Expanded `--plan` Output

`queue --plan --json` must return:

- tasks selected
- tasks skipped
- skip reason per task
- locks involved
- workspace paths

This enables dry-run scheduling validation.

---

## Non-Goals

- background scheduling
- retry loops
- persistent state beyond files
- analytics dashboards

---

## Success Criteria

- users can trust `queue` under concurrency
- failures are explainable post-mortem
- shell scripts can reason via exit codes
- no task accidentally runs twice

---

Target release: **Village v1.2**
