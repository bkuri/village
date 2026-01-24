# Village Examples

This directory contains practical examples for using Village, ranging from basic first-task workflows to advanced multi-day operations.

## Quick Start Examples

**First Task** - Your first task ever with Village
- See: [01-quickstart/first-task.md](01-quickstart/first-task.md)
- Covers: Setup, first resume, basic cleanup

## Configuration Examples

**Custom Agent** - Define a specialized build agent
- See: [02-configuration/custom-agent.md](02-configuration/custom-agent.md)

**Multiple Agents** - Configure build, frontend, and test agents
- See: [04-configuration/multiple-agents.md](04-configuration/multiple-agents.md)

## Command Examples

**Queue Multiple** - Queue tasks across different agents
- See: [03-commands/queue-multiple.md](03-commands/queue-multiple.md)

## Advanced Examples

**Multi-Day Workflow** - Interrupt recovery, stale lock cleanup, corrupted locks
- See: [05-advanced/workflow.md](05-advanced/workflow.md)

## Running Examples

All examples assume you're in a Git repository with Village installed.

```bash
cd /path/to/your/repo

# Ensure Village is initialized
village up

# Check readiness
village ready

# Follow an example
# (Copy commands from example files)
```

## Common Patterns

### Starting Clean

```bash
# Clean slate: stop runtime, cleanup, restart
village down
village cleanup --apply
village up
```

### Inspecting State

```bash
# Quick status check
village status --short

# Detailed workers view
village status --workers

# Orphan detection
village status --orphans
```

### Queue Operations

```bash
# Preview queue plan
village queue --n 3 --dry-run

# Execute queue
village queue --n 3

# Queue specific agent type
village queue --agent build --n 2
```

### Resume Operations

```bash
# Explicit resume
village resume bd-a3f8

# Resume with agent
village resume bd-a3f8 --agent frontend

# Detached resume
village resume bd-a3f8 --detached

# Planner mode (no task ID)
village resume
```

## Contributing

To add new examples:

1. Determine the appropriate category (quickstart, configuration, commands, advanced)
2. Create the markdown file in that subdirectory
3. Add a brief entry to this README with description
4. Ensure example is self-contained (no dependencies on other examples)
