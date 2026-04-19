# Village v2.2.0

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

## What changed since v2.1.0

v2.1.0 laid the foundation: standalone task store, role-based CLI, spec-driven build loop, ACP integration. v2.2.0 is the polish pass — documentation accuracy, test quality, and the first-time user experience.

If you're already running v2.1.0, everything works the same. This is a safe upgrade.

### New: 5-minute demo in the README

The README now has a complete walkthrough from `pip install` to shipping. Install, create a project, define tasks, plan, build, watch, crash and recover, release — each section is 3-5 lines. No prerequisites beyond Python, git, and tmux.

### New: Village vs Manual comparison

A 7-row table comparing manual coordination (Slack messages, terminal-hopping, post-it notes) against Village's one-command answers. Conclusion: *Village makes coordination boring. Boring is reliable.*

### Documentation cleanup

Every reference to the removed Beads dependency has been purged — quickstart, man page, roadmap, changelog, extensibility docs, templates, examples. The ROADMAP resolved contradictions and duplicated sections. The CHANGELOG fixed the half-completed `elder` → `scribe` rename. The man page (`village.1.md`) was rewritten to match the current role-based CLI surface. The PKGBUILD was updated for hatch-vcs builds.

### Test suite overhaul

- **Deleted 197 tests** that verified Python language features (dataclass field assignment, identity functions, Click color calls) rather than Village behavior
- **Converted 9 mock-heavy queue tests** to use real filesystem and real git repos instead of MagicMock chains
- **Added 5 end-to-end integration tests** proving core guarantees: full task lifecycle, concurrent isolation, crash recovery, rollback on failure, queue deduplication
- **Converted 35 render tests** from mock-assert to output verification
- **Audited the remaining 1,869 tests** — 75% clean, 14% minor, 8% moderate, 3% severe. Full findings documented in `tests/MOCK_AUDIT.md`

### Quality

- **2,150 tests**, 0 failures, 28-second suite
- Clean lint (`ruff`), strict type checking (`mypy --strict`)
- CI pipeline: lint → type check → test → build → publish
- Bump label enforcement on every PR

---

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

## The rest of the story

The features below shipped in v2.1.0 and are unchanged in v2.2.0. Included here for completeness.

### Role-based CLI

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

```bash
village planner design "Add OAuth2 with Google"
village planner inspect --fix
village builder run -p 3
```

### ACP integration

```bash
village acp  # stdio agent for editors
```

### Extensibility framework

7 extension points: `ChatProcessor`, `ToolInvoker`, `ThinkingRefiner`, `ChatContext`, `TaskHooks`, `ServerDiscovery`, `LLMProviderAdapter`.

## Upgrade from v1.x

**Breaking changes:**

- Beads client dependency removed — use `village tasks` instead of `bd` commands
- CLI restructured from flat commands to role-based groups

**Migration:**

- `bd create` → `village tasks create`
- `bd ready` → `village tasks ready`
- `bd list` → `village tasks list`
- `village queue` → `village builder queue`
- `village resume <id>` → `village builder resume --task <id>`

## Full changelog

See [CHANGELOG.md](https://github.com/bkuri/village/blob/master/CHANGELOG.md) for the complete history.

---

## Philosophy

Village is intentionally boring. It does not hide execution. It does not predict intent. It does not require belief. It simply coordinates reality.

The pane exists or it doesn't. The lock file is there or it isn't. The event log says what happened. No magic, no faith, no surprises.

We hope you find it useful.

— Bernardo
