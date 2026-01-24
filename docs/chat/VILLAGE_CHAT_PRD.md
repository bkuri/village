# Village PRD — `village chat` (v1.x)

## Status
Draft — targeted for v1.x (non-invasive, optional feature)

---

## Purpose

`village chat` provides a **human-in-the-loop conversational workspace**
for defining, refining, and sharing project knowledge.

It enables structured discussion and grounding **without executing work**.

This command exists to solve alignment — not orchestration.

---

## Core Principle

> `village chat` creates understanding, not side effects.

It must never:

- spawn agents
- create or modify Beads tasks
- invoke tmux
- acquire locks
- schedule execution
- mutate runtime state

All outputs are files.

---

## High-Level Flow

```
village chat
   ↓
guided conversation (PPC-driven)
   ↓
optional user-invoked subcommands
   ↓
synthesis
   ↓
write structured context files
   ↓
exit
```

No background processes.
No persistent chat memory beyond files.

---

## Outputs

All outputs are markdown files.

Default directory:

```
.village/context/
```

Example structure:

```
.village/context/
  project.md
  goals.md
  constraints.md
  assumptions.md
  decisions.md
  open-questions.md
```

---

## Conversational Subcommands

`village chat` supports **explicit, user-invoked subcommands**
for grounding discussion in real project state.

Subcommands are:

- allowlisted
- intent-based
- read-only in v1.x

They are not raw shell passthrough.

---

## Subcommand Grammar

```
/<command> [args]
```

Examples:

```
/tasks
/task build-api
/ready
/status
/help
/help tasks
```

Subcommands may only be executed when explicitly typed by the user.

The assistant may suggest commands, but never invoke them automatically.

---

## Initial Subcommand Set (v1.x)

| Command | Description | Backend |
|--------|-------------|---------|
| `/tasks` | List all tasks | `bd list` |
| `/task <id>` | Show task details | `bd show <id>` |
| `/ready` | Show ready tasks | `bd ready` |
| `/status` | Village runtime summary | `village status --short` |
| `/help [topic]` | Show chat help (optionally for a topic) | internal |

### `/help` topics (v1)
- `commands` (default)
- `tasks`
- `context`
- `files`
- `policy`
- `workflow`

---

## Why Intent-Based Commands

Commands are defined by **meaning**, not by implementation.

Example:

```
/tasks
```
means:
> “show the tasks that exist”

not:
> “run bd list”

This allows:

- friendly UX
- stable interface even if tools change
- safer allowlisting
- consistent formatting

---

## Subcommand Execution Rules

- read-only only (v1.x)
- stdout and stderr captured verbatim
- output injected back into conversation as context
- no command chaining
- no shell evaluation

---

## Example Injection Format

```
### Subcommand: /tasks

stdout:
<output>

stderr:
<output>
```

---

## Success Criteria

- projects can be bootstrapped faster
- shared understanding is explicit and durable
- agents receive consistent grounding
- users can refine intent incrementally
- zero impact on runtime stability

---

## Summary

`village chat` is:

- lightweight
- deterministic
- file-backed
- human-centered
- safe by default

It turns Village from a task orchestrator into a **thinking surface
for parallel development** — without compromising any existing guarantees.