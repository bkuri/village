# Multi-Day Workflow

This example demonstrates handling interrupts, stale locks, and corrupted locks over multiple days.

## Day 1: Start Work

```bash
# Morning: Initialize and start first task
cd /path/to/repo
village up
village ready

# Queue a build task
village queue --agent build --n 1
village status --workers
```

## Day 1: Interrupted Resume (Ctrl+C)

While working on a task, press Ctrl+C to interrupt:

```bash
# This simulates interrupt during execution
village resume bd-a3f8 --agent build
# (Press Ctrl+C while OpenCode is running)
```

**What happens:**
- OpenCode stops
- Resources remain (worktree, lock file, tmux window)
- Message logged: "Resume interrupted by user"
- Exit code: 2 (not ready)

## Day 1: Check for Orphans

After interrupt, check what was left behind:

```bash
# Orphaned resources will appear here
village status --orphans
```

Expected output:
```
ORPHANS (2):
  STALE LOCKS (1):
    bd-a3f8 (pane: %12)
  UNTRACKED WORKTREES (1):
    .worktrees/bd-a3f8
```

## Day 1: Clean Up Orphans

Remove the orphaned resources from interrupt:

```bash
# Plan cleanup (dry-run)
village cleanup

# Execute cleanup
village cleanup --apply
```

Expected output:
```
CLEANUP PLAN
=============

Remove 1 stale lock file?
  .village/locks/bd-a3f8.lock

Remove 1 untracked worktree?
  .worktrees/bd-a3f8

Run: village cleanup --apply
```

## Day 1: Continue Work

Start fresh after cleanup:

```bash
# Resume a different task
village queue --n 1
village status --workers
```

## Day 2: Corrupted Lock Recovery

Simulate a corrupted lock file:

```bash
# Manually create a corrupted lock
echo "corrupted=invalid" > .village/locks/bd-corrupted.lock

# Check status - corrupted lock will be logged
village status --locks
```

Expected output (error in logs):
```
Corrupted lock .village/locks/bd-corrupted.lock: missing field 'id'
Corrupted lock .village/locks/bd-corrupted.lock: missing field 'pane'
```

## Day 2: Handle Corrupted Lock

Remove corrupted lock manually:

```bash
# Option 1: Use unlock command
village unlock bd-corrupted --force

# Option 2: Manual removal
rm .village/locks/bd-corrupted.lock
```

## Day 2: Verify Cleanup

```bash
# Check for remaining orphans
village status --orphans

# Should show no orphans
```

Expected output:
```
No orphans found
```

## Day 2: Full Production Workflow

Combine all patterns in a real workflow:

```bash
# Initialize for the day
village up

# Check readiness
village ready

# Queue multiple tasks
village queue --n 3

# Monitor progress
village status --workers

# Handle interrupts if they occur
# (Use Ctrl+C gracefully)

# End of day: cleanup any orphans
village cleanup --apply

# Stop runtime when done
village down
```

## Recovery Best Practices

### 1. Always Check Status After Interrupt

```bash
# After any interrupt:
village status --orphans
village status --workers
```

### 2. Clean Up Before New Work

```bash
# Always cleanup before starting new tasks
village cleanup --apply
village queue --n 1
```

### 3. Use Planner for Next Action

```bash
# Let Village suggest next step
village resume

# Output will suggest one of:
# - "Action: village up"
# - "Action: village status"
# - "Action: village queue"
```

### 4. Monitor Logs for Warnings

```bash
# Run with verbose logging to see all warnings
village --verbose queue --n 1

# Check logs for:
# - "Corrupted lock .village/locks/..."
# - "Resources remain for manual cleanup: ..."
```

## Corrupted Lock Prevention

### 1. Don't Manually Edit Lock Files

Lock files are internal state. Let Village manage them.

### 2. Use Supported Operations

```bash
# Correct: Use village commands
village resume bd-a3f8
village unlock bd-a3f8
village cleanup

# Incorrect: Direct file manipulation
rm .village/locks/bd-a3f8.lock
echo "id=..." > .village/locks/bd-a3f8.lock
```

### 3. Report Corrupt Locks

If you encounter corrupted locks regularly:

1. Enable verbose logging: `village --verbose <command>`
2. Check for disk issues: `fsck` (if applicable)
3. Check for concurrent access: `village status --locks` while another command runs

## Exit Code Reference

When working across multiple days, pay attention to exit codes:

| Exit Code | Meaning | Action |
|-----------|----------|--------|
| 0 | Success | Continue to next task |
| 2 | Not ready / interrupted | Check status, cleanup orphans |
| 1 | Error | Review error message, fix issue |
| 3 | Blocked | No tasks available, wait |
| 4 | Partial success | Retry failed tasks |

## Full Day Example Script

```bash
#!/bin/bash
#一天的 Village workflow

echo "=== Morning Setup ==="
village up
village ready

echo "=== Queue Tasks ==="
village queue --n 3

echo "=== Monitor Progress ==="
village status --workers

echo "=== End of Day ==="
village status --orphans
village cleanup --apply

echo "=== Shut Down ==="
village down
```

## Next Steps

Try these examples:

1. [First Task](../01-quickstart/first-task.md) - Basic single-day workflow
2. [Custom Agent](../02-configuration/custom-agent.md) - Single agent setup
3. [Queue Multiple](../03-commands/queue-multiple.md) - Queue across agent types
4. [Multiple Agents](../04-configuration/multiple-agents.md) - Multi-agent configuration
