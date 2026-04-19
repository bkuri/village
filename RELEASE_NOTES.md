# Village v2.1.0

> **A tiny operating system for parallel development.**

It started with a question: *why can't I just run three AI agents on three tasks without things falling apart?*

The answer turned out to be the same answer it always is in software: coordination is hard, and most tools either hide it from you (magic) or make you do it yourself (ceremony). Village takes a third path — it makes coordination **boring**. Boring is reliable. Boring is auditable. Boring lets you focus on the code.

---

## What is Village?

Village orchestrates multiple AI agents working in parallel on your local machine. It doesn't run in the cloud. It doesn't need a database. It doesn't have a daemon.

It uses three things you already trust:

- **tmux** — if a pane exists, work exists. If it doesn't, it doesn't.
- **git worktrees** — each agent works in isolation. No conflicts.
- **Your task store** — what work is ready, what's blocked, what's done.

Everything is a file. Everything is inspectable. Everything survives a crash.

## What's new in v2.1.0

This release is the culmination of months of iteration — from a bash script to a 31K-line Python codebase with 2,150 tests, a spec-driven build loop, and a philosophy that refuses to hide state.

### The big story: standalone and self-contained

Village no longer depends on an external task manager. The native task store (`village tasks`) handles dependencies, priorities, labels, search, and atomic operations — all backed by a JSONL file. No Cargo, no external database, no extra install step.

```bash
village tasks create "Add authentication" --type feature -p 1
village tasks create "Write auth tests" --type task --depends-on <id>
village tasks ready
```

### Role-based CLI

The flat command surface is gone. Village now speaks in roles — each with its own greeting, skills, and cross-routing:

| Role | Job |
|------|-----|
| `village planner` | Design specs, inspect for cross-cutting issues |
| `village builder` | Autonomous spec-driven build loop |
| `village watcher` | Real-time observability, cleanup, audit trails |
| `village scribe` | Knowledge base: fetch, ask, curate |
| `village council` | Multi-persona deliberation |
| `village doctor` | Health diagnostics and prescriptions |
| `village greeter` | Q&A triage, routes to other roles |

### Spec-driven build loop

The planner decomposes goals into numbered markdown specs with acceptance criteria. The builder picks them up one at a time (or in parallel with `-p N`), spins up an AI agent in an isolated git worktree, and loops until every spec is `COMPLETE`.

```bash
village planner design "Add OAuth2 with Google"
village planner inspect --fix
village builder run -p 3
```

If an agent fails, Village rolls back the worktree and retries. If your terminal crashes, `village watcher cleanup --apply` picks up where you left off.

### ACP integration

Village speaks the Agent Client Protocol. Use it as an ACP agent in your editor (Zed, JetBrains) or as a client to orchestrate external agents (Claude Code, Gemini CLI).

```bash
village acp  # stdio agent for editors
```

### Extensibility framework

7 extension points for domain customization without forking:

- `ChatProcessor` — pre/post message processing
- `ToolInvoker` — customize MCP tool invocation
- `ThinkingRefiner` — domain-specific query refinement
- `ChatContext` — session state management
- `TaskHooks` — customize task lifecycle
- `ServerDiscovery` — dynamic MCP server discovery
- `LLMProviderAdapter` — customize LLM provider config

### Quality

- **2,150 tests**, 0 failures, 27-second suite
- Clean lint (`ruff`), strict type checking (`mypy --strict`)
- CI pipeline: lint → type check → test → build → publish
- Bump label enforcement on every PR

## Getting started

```bash
pip install village-ai

mkdir my-project && cd my-project && git init
village up

village tasks create "Add CLI entry point"
village tasks create "Add tests"
village tasks create "Add README"

village builder run -p 3
```

See the [5-minute demo](https://github.com/bkuri/village#5-minute-demo) in the README for the full walkthrough.

## Upgrade from v1.x

**Breaking changes:**

- Beads client dependency removed — use `village tasks` instead of `bd` commands
- CLI restructured from flat commands to role-based groups (`village builder run` instead of `village run`)
- `village/chat/beads_client.py` and `village/probes/beads.py` removed
- `village/cli.py` monolith replaced by `village/cli/` package

**Migration:**

- Replace `bd create` → `village tasks create`
- Replace `bd ready` → `village tasks ready`
- Replace `bd list` → `village tasks list`
- Replace `village queue` → `village builder queue`
- Replace `village resume <id>` → `village builder resume --task <id>`
- Run `village doctor diagnose` to verify your setup

## Full changelog

See [CHANGELOG.md](https://github.com/bkuri/village/blob/master/CHANGELOG.md) for the complete history.

---

## Philosophy

Village is intentionally boring. It does not hide execution. It does not predict intent. It does not require belief. It simply coordinates reality.

The pane exists or it doesn't. The lock file is there or it isn't. The event log says what happened. No magic, no faith, no surprises.

We hope you find it useful.

— Bernardo
