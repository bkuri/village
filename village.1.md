# VILLAGE(1)

## NAME

village \- CLI-native parallel development orchestrator

## SYNOPSIS

**village** [**COMMAND**] [**OPTIONS**]

## DESCRIPTION

Village orchestrates multiple AI agents working in parallel — safely, locally, and transparently — using tools you already trust:
  - **Built-in task store** for task readiness and dependencies
  - **tmux** for runtime truth and observability
  - **git worktrees** for isolation
  - **OpenCode** for execution

No daemon. No database. No hidden state.

## COMMANDS

**Task Management** (village tasks)
  tasks create      Create a new task.
  tasks delete      Delete a task.
  tasks update      Update a task (status, title, description, priority, labels).
  tasks list        List tasks.
  tasks show        Show task details.
  tasks ready       Show tasks ready to work (unblocked).
  tasks search      Search tasks by keyword.
  tasks count       Count tasks.
  tasks deps        Show task dependencies.
  tasks label       Add or remove labels from a task.

**Spec-Driven Development** (village builder)
  builder run       Run the autonomous spec-driven build loop.
  builder status    Show build loop status.
  builder pause     Pause an in-progress task.
  builder resume    Resume a build loop or a paused task.
  builder queue     Queue and execute ready tasks.
  builder arrange   Arrange tasks into stacked PRs based on stack labels.
  builder rollback  Rollback the current plan (emergency abort).

**Spec Management** (village planner)
  planner design    Design a new workflow interactively.
  planner refine    Refine an existing workflow interactively.
  planner resume    Resume editing a draft plan with an interactive interview.
  planner approve   Approve a plan and create worktree to start development.
  planner list      List all plans.
  planner show      Display workflow steps.
  planner plan      Show plan details.
  planner delete    Delete a plan.
  planner inspect   Review specs for cross-cutting issues.
  planner workflows List available workflow templates.

**Knowledge Base** (village scribe)
  scribe fetch      Ingest a URL or file into the knowledge base.
  scribe ask        Query the knowledge base and synthesize an answer.
  scribe curate     Health check and maintain the knowledge base.
  scribe drafts     List or count draft tasks.

**Observation** (village watcher)
  watcher status      Show village status.
  watcher ready       Check if village is ready for work.
  watcher dashboard   Show real-time dashboard of Village state.
  watcher events      Show recent events.
  watcher locks       List all locks with ACTIVE/STALE status.
  watcher unlock      Unlock a task (remove lock file).
  watcher cleanup     Remove stale locks and optionally remove orphan/stale worktrees.
  watcher monitor     Watch wiki/ingest/ for new files and process them.
  watcher ledger show View audit trail for a task.
  watcher ledger list List tasks with audit trails.

**Multi-Persona Deliberation** (village council)
  council debate  Start a council debate on a topic.
  council list    List past councils.
  council show    Show a council transcript.

**Health Diagnostics** (village doctor)
  doctor diagnose   Run project health diagnostics.
  doctor prescribe  Generate recommendations from diagnosis results.

**Goals** (village goals)
  goals             Show goal hierarchy from GOALS.md.

**Project Onboarding** (village greeter)
  greeter           Run onboarding interview with adaptive prompts.
  welcome           Alias for greeter.
  chat              Alias for greeter.

**Lifecycle** (village new / village up / village down)
  new               Create a new project with village support.
  up                Initialize village runtime (idempotent).
  down              Stop village runtime (kill tmux session).

## OPTIONS

**Global**
  --verbose, -v         Verbose logging
  --transport MODE      Start transport daemon mode (cli|telegram|acp|stdio)
  --version             Show version and exit
  --help, -h            Show help message and exit

## EXAMPLES

**Create a project with Village support**
```bash
village new myproject
```

**Initialize village in an existing project**
```bash
village up
```

**Run spec-driven development loop**
```bash
village builder run
```

**Check tasks ready to work**
```bash
village tasks ready
```

**View Village dashboard**
```bash
village watcher dashboard --watch
```

**Run health diagnostics**
```bash
village doctor
```

## SEE ALSO

**tmux(1)**      Terminal multiplexer
**git(1)**       Version control system
**opencode(1)**  AI coding agent

## FILES

.village/config              Project-level configuration (INI format)
.village/*                   Village state directory
.village/locks/*             Lock files
.village/plans/*             Plan files
.worktrees/*                 Git worktrees
GOALS.md                     Project goal hierarchy

## BUGS

Report bugs at: https://github.com/bkuri/village/issues

## AUTHOR

Bernardo Kuri <bkuri@bkuri.com>

## COPYRIGHT

Copyright © 2026 Bernardo Kuri

MIT License
