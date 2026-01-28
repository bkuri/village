# VILLAGE(1)

## NAME

village \- CLI-native parallel development orchestrator

## SYNOPSIS

**village** [**COMMAND**] [**OPTIONS**]

## DESCRIPTION

Village orchestrates multiple AI agents working in parallel — safely, locally, and transparently — using tools you already trust:
  - **Beads** for task readiness and dependencies
  - **tmux** for runtime truth and observability
  - **git worktrees** for isolation
  - **OpenCode** for execution
  - **PPC** (optional) for deterministic contracts

No daemon. No database. No hidden state.

## COMMANDS

**Task Management**
  queue                Queue task to first available worker
  dequeue              Remove task from queue
  resume-task          Resume paused task
  cancel-task         Cancel running task
  status               Show Village status
  dashboard            Show real-time dashboard

**Chat**
  chat                 Start LLM-native conversational interface for task creation
                      Supports task decomposition via Sequential Thinking

**Cleanup**
  cleanup              Remove stale locks and optionally remove orphans

**Drafts Management**
  drafts               List draft tasks

## OPTIONS

**Global**
  --config PATH         Specify Village config directory
  --help, -h         Show help message and exit
  --version, -v        Show version and exit

## EXAMPLES

**Create a task**
```bash
village chat
> /create Add Redis caching
> /confirm
```

**Show status**
```bash
village status
```

**View dashboard**
```bash
village dashboard --watch
```

## SEE ALSO

**beads(1)**     Task management system  
**tmux(1)**      Terminal multiplexer
**git(1)**       Version control system

## FILES

~/.config/village/config.toml     Village configuration
.village/*                     Village state directory
.village/locks/*               Lock files
.village/worker-trees/*         Git worktrees

## BUGS

Report bugs at: https://github.com/bkuri/village/issues

## AUTHOR

Bernardo Kuri <bkuri@bkuri.com>

## COPYRIGHT

Copyright © 2026 Bernardo Kuri

MIT License
