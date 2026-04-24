# Multi-Day Workflow

This example demonstrates handling interrupts, stale locks, and corrupted locks over multiple days.

## Day 1: Start Work

```bash
# Morning: Initialize and start first task
cd /path/to/repo
village up
village watcher ready

# Queue a build task
village builder queue --agent build --n 1
village watcher status --system
```

## Day 1: Interrupted Resume (Ctrl+C)

While working on a task, press Ctrl+C to interrupt:

```bash
# This simulates interrupt during execution
village builder resume --task village-t1 --agent build
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
village watcher status --system
```

Expected output:
```
ORPHANS (2):
  STALE LOCKS (1):
    village-t1 (pane: %12)
  UNTRACKED WORKTREES (1):
    .worktrees/village-t1
```

## Day 1: Clean Up Orphans

Remove the orphaned resources from interrupt:

```bash
# Plan cleanup (dry-run)
village watcher cleanup

# Execute cleanup
village watcher cleanup --apply
```

Expected output:
```
CLEANUP PLAN
=============

Remove 1 stale lock file?
  .village/locks/village-t1.lock

Remove 1 untracked worktree?
  .worktrees/village-t1

Run: village watcher cleanup --apply
```

## Day 1: Continue Work

Start fresh after cleanup:

```bash
# Resume a different task
village builder queue --n 1
village watcher status --system
```

## Day 2: Corrupted Lock Recovery

Simulate a corrupted lock file:

```bash
# Manually create a corrupted lock
echo "corrupted=invalid" > .village/locks/village-corrupted.lock

# Check status - corrupted lock will be logged
village watcher locks
```

Expected output (error in logs):
```
Corrupted lock .village/locks/village-corrupted.lock: missing field 'id'
Corrupted lock .village/locks/village-corrupted.lock: missing field 'pane'
```

## Day 2: Handle Corrupted Lock

Remove corrupted lock manually:

```bash
# Option 1: Use unlock command
village watcher unlock village-corrupted --force

# Option 2: Manual removal
rm .village/locks/village-corrupted.lock
```

## Day 2: Verify Cleanup

```bash
# Check for remaining orphans
village watcher status --system

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
village watcher ready

# Queue multiple tasks
village builder queue --n 3

# Monitor progress
village watcher status --system

# Handle interrupts if they occur
# (Use Ctrl+C gracefully)

# End of day: cleanup any orphans
village watcher cleanup --apply

# Stop runtime when done
village down
```

## Recovery Best Practices

### 1. Always Check Status After Interrupt

```bash
# After any interrupt:
village watcher status --system
village watcher status --system
```

### 2. Clean Up Before New Work

```bash
# Always cleanup before starting new tasks
village watcher cleanup --apply
village builder queue --n 1
```

### 3. Use Planner for Next Action

```bash
# Let Village suggest next step
village watcher ready

# Output will suggest one of:
# - "Action: village up"
# - "Action: village watcher status"
# - "Action: village builder queue"
```

### 4. Monitor Logs for Warnings

```bash
# Run with verbose logging to see all warnings
village --verbose builder queue --n 1

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
village builder resume --task village-t1
village watcher unlock village-t1
village watcher cleanup

# Incorrect: Direct file manipulation
rm .village/locks/village-t1.lock
echo "id=..." > .village/locks/village-t1.lock
```

### 3. Report Corrupt Locks

If you encounter corrupted locks regularly:

1. Enable verbose logging: `village --verbose <command>`
2. Check for disk issues: `fsck` (if applicable)
3. Check for concurrent access: `village watcher locks` while another command runs

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
village watcher ready

echo "=== Queue Tasks ==="
village builder queue --n 3

echo "=== Monitor Progress ==="
village watcher status --system

echo "=== End of Day ==="
village watcher status --system
village watcher cleanup --apply

echo "=== Shut Down ==="
village down
```

## Next Steps

Try these examples:

1. [First Task](../01-quickstart/first-task.md) - Basic single-day workflow
2. [Custom Agent](../02-configuration/custom-agent.md) - Single agent setup
3. [Queue Multiple](../03-commands/queue-multiple.md) - Queue across agent types
4. [Multiple Agents](../04-configuration/multiple-agents.md) - Multi-agent configuration
