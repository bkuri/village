# Village Quickstart Guide

A practical guide to setting up Village for your development workflow.

---

## What is Village?

Village is a **tiny operating system for parallel development**. It orchestrates multiple AI agents working simultaneously on your local machine — safely, transparently, and without hidden state.

### The Problem

Your dev team has 10 tasks ready. Without Village:

- Dev 1 manually starts task 1 in a terminal
- Dev 2 waits to see which task becomes available next
- Dev 3 resumes yesterday's interrupted task
- Nobody knows who's working on what
- Coordination happens via Slack — error-prone and slow
- If a terminal crashes, work is duplicated or lost

### The Solution

With Village:

```bash
# Start 3 parallel tasks in background
village queue --n 3

# See all active workers (who's doing what)
village status --workers

# Attach to a task
village resume bd-a3f8

# Clean up stale locks if something crashed
village cleanup --apply
```

That's it. Automatic, observable, recoverable. Village uses:
- **Beads** for task readiness and dependencies
- **tmux** for runtime truth (if a pane exists, work exists)
- **git worktrees** for isolation
- **OpenCode** for agent execution

---

## Choose Your Path

Village supports different project states. Which describes yours?

### Quick Self-Assessment

**Do you have Beads tasks ready?**
- No → Go to **[Path A: Brand New Project](#path-a-brand-new-project)**
- Yes → Continue to next question

**Is Village already initialized in your repo?**
- No → Go to **[Path B: Existing Project with Beads](#path-b-existing-project-with-beads)**
- Yes → Go to **[Path C: Existing Project with Village](#path-c-existing-project-with-village)**

---

## Path A: Brand New Project

**Time: 15 minutes** | **Prerequisites: Git repo, Python 3.11+, tmux**

### Prerequisites Checklist

- [ ] Git repository exists (`git init` or clone your repo)
- [ ] Python 3.11 or later installed
- [ ] tmux installed (`which tmux` should return a path)
- [ ] uv (Python package manager) installed for easy Village installation

### Step 1: Install Village and Beads

```bash
cd /path/to/your/repo

# Install Village using uv
uv pip install -e .

# Install Beads (task DAG manager)
cargo install beads
```

**Version Note:** Village v1.3+ supports Jujutsu (jj). If using jj instead of Git, see "Version Notes" at the end of this guide.

### Step 2: Initialize Village Runtime

```bash
# Start Village (creates tmux session, .village/ directory)
village up

# Check if everything is ready
village ready
```

Expected output:
```
Environment: ✅ Runtime
          ✅ Git repo
Work Available: ❌ Beads not initialized
```

If you see "Beads not initialized," initialize it:

```bash
bd init
```

### Step 3: Create Your First Task

Village makes it easy to create and manage Beads tasks. Use either:

```bash
# Option A: Interactive task creation
village add

# Option B: Chat-based task creation with AI assistance
village chat
```

These tools will guide you through creating a Beads task with proper dependencies. Behind the scenes, Village is using Beads commands to manage your task DAG.

**Manual Beads commands (if you prefer):**
```bash
# View available tasks
bd list

# Create a task (if using Beads directly)
bd create "Add user authentication" --depends-on bd-previous-task

# Check ready tasks
bd ready
```

### Step 4: Queue and Start Your Task

```bash
# Start 1 ready task
village queue --n 1
```

Expected output:
```
Starting 1 task(s)...

Tasks started: 1
Tasks failed: 0
```

### Step 5: Inspect the Running Worker

```bash
# See all active workers
village status --workers
```

Expected output:
```
TASK_ID    STATUS    PANE     AGENT   WINDOW            CLAIMED_AT
bd-a3f8    ACTIVE    %12      worker  worker-1-bd-a3f8  2026-01-25 10:30:45
```

### Step 6: Resume and Work on the Task

```bash
# Attach to the worker pane
village resume bd-a3f8
```

You're now inside a tmux pane with OpenCode running on your task. Work on it as needed.

When done with the task (or want to leave it running in background):
- Press `Ctrl+B` then `D` to detach from tmux (task keeps running)
- Or close the pane to stop the task

### Step 7: Clean Up (Optional)

```bash
# Stop the runtime
village down

# Clean up any stale locks or orphaned worktrees
village cleanup --apply
```

### Validation Checklist

- [ ] `village up` completed without errors
- [ ] `village ready` shows all checks passing
- [ ] `village add` or `village chat` created a task
- [ ] `village queue --n 1` started a task
- [ ] `village status --workers` shows your task as ACTIVE
- [ ] `village resume bd-a3f8` let you attach to the task
- [ ] `village down` and `village cleanup --apply` cleaned up properly

---

## Path B: Existing Project with Beads

**Time: 10 minutes** | **Prerequisites: Beads installed, tasks ready, Git repo**

### Prerequisites Checklist

- [ ] Beads is installed and initialized (`bd ready` shows tasks)
- [ ] Git repository exists
- [ ] Python 3.11+ and tmux installed

### Step 1: Install Village

```bash
cd /path/to/your/repo

uv pip install -e .
```

### Step 2: Initialize Village Runtime

```bash
# Start Village (creates tmux session, .village/ directory)
village up

# Check readiness
village ready
```

Expected output:
```
Environment: ✅ Runtime
          ✅ Git repo
Work Available: ✅ Beads ready (X tasks available)
```

### Step 3: Queue Ready Tasks

```bash
# Start 3 parallel tasks
village queue --n 3
```

Village will:
1. Query Beads for ready tasks (`bd ready`)
2. Create git worktrees for isolation
3. Spawn OpenCode agents in tmux panes
4. Track everything with lock files

### Step 4: Inspect Running Workers

```bash
# See all active workers
village status --workers
```

Expected output:
```
TASK_ID    STATUS    PANE     AGENT   WINDOW            CLAIMED_AT
bd-a3f8    ACTIVE    %12      worker  worker-1-bd-a3f8  2026-01-25 10:30:45
bd-b7c2    ACTIVE    %13      worker  worker-2-bd-b7c2  2026-01-25 10:30:46
bd-d9e4    ACTIVE    %14      worker  worker-3-bd-d9e4  2026-01-25 10:30:47
```

### Step 5: Resume a Task

```bash
# Attach to a specific task
village resume bd-a3f8
```

### Validation Checklist

- [ ] `village up` completed without errors
- [ ] `village ready` shows Beads ready with tasks available
- [ ] `village queue --n 3` started tasks
- [ ] `village status --workers` shows active workers
- [ ] `village resume bd-a3f8` let you attach to a task

---

## Path C: Existing Project with Village

**Time: 5 minutes** | **Prerequisites: Village already running**

### Prerequisites Checklist

- [ ] Village is already initialized (`.village/` directory exists)
- [ ] tmux session is running (`tmux list-sessions` shows "village")

### Step 1: Verify Readiness

```bash
# Quick status check
village status --short
```

Expected output:
```
Runtime: ✅ Active (village session)
Locks: 0 active, 0 stale
```

### Step 2: Queue More Tasks or Resume Existing

```bash
# Queue more ready tasks
village queue --n 3

# Or resume a specific task
village resume bd-a3f8

# Or see all workers
village status --workers
```

### Common Daily Workflows

**Morning workflow:**
```bash
# Check status
village status --short

# Queue new tasks
village queue --n 3

# Resume yesterday's task
village resume bd-a3f8
```

**End-of-day workflow:**
```bash
# See what's still running
village status --workers

# Detach from all tasks (Ctrl+B, D in tmux)

# Shutdown runtime
village down
```

**Recovery after crash:**
```bash
# Check for orphans (stale locks, untracked worktrees)
village status --orphans

# Clean up
village cleanup --apply

# Restart
village up
village queue --n 3
```

### Jump to Examples

For deeper dives and advanced workflows:
- [Custom Agent Configuration](docs/examples/02-configuration/custom-agent.md)
- [Queue Multiple Tasks](docs/examples/03-commands/queue-multiple.md)
- [Multiple Agents](docs/examples/04-configuration/multiple-agents.md)
- [Multi-Day Workflow](docs/examples/05-advanced/workflow.md)

---

## Basic Functionality Showcase

### Scenario: "You Have 3 Ready Tasks"

Here's the complete workflow from start to finish:

#### 1. Queue Tasks

```bash
# Start 3 parallel tasks
village queue --n 3
```

Output:
```
Starting 3 task(s)...

Tasks started: 3
Tasks failed: 0
```

#### 2. Inspect Workers

```bash
# See all active workers
village status --workers
```

Output:
```
TASK_ID    STATUS    PANE     AGENT   WINDOW            CLAIMED_AT
bd-a3f8    ACTIVE    %12      worker  worker-1-bd-a3f8  2026-01-25 10:30:45
bd-b7c2    ACTIVE    %13      worker  worker-2-bd-b7c2  2026-01-25 10:30:46
bd-d9e4    ACTIVE    %14      worker  worker-3-bd-d9e4  2026-01-25 10:30:47
```

#### 3. Resume a Task

```bash
# Attach to task bd-a3f8
village resume bd-a3f8
```

Now you're inside the tmux pane with OpenCode. Work on the task as needed.

#### 4. Handle Interrupts Gracefully

If your terminal crashes or you press `Ctrl+C` while `village queue` is running:

```bash
# Check what's orphaned
village status --orphans
```

Output:
```
Orphans detected:
- Stale locks: 2
- Untracked worktrees: 1

Run: village cleanup --apply to remove them
```

```bash
# Clean up
village cleanup --apply
```

#### 5. Key Patterns Summary

| Command | Purpose | When to Use |
|---------|---------|-------------|
| `village up` | Initialize runtime | First time or after `village down` |
| `village queue --n N` | Start N parallel tasks | Have ready tasks, want parallel work |
| `village status --workers` | See all active workers | Monitoring, debugging |
| `village resume <task-id>` | Attach to a task | Work on a specific task |
| `village cleanup --apply` | Clean up stale locks | After crashes, interrupts |
| `village down` | Stop runtime | End of day, maintenance |

---

## Configuration & Project Templates

### Do You Need Custom Agents?

Village works out-of-the-box with a default `worker` agent. But most teams benefit from specialized agents:

**Question:** "Do you have different types of work?"
- Backend changes, frontend changes, testing, documentation → **YES, customize agents**
- Just one type of work → **NO, use default agent**

If you need custom agents, see:
- [Custom Agent Guide](docs/examples/02-configuration/custom-agent.md) — Define your first custom agent
- [Multiple Agents Guide](docs/examples/04-configuration/multiple-agents.md) — Use several specialized agents together
- [Project Templates](#project-templates) — Pre-configured setups for common project types

### Project Templates

Village includes pre-configured templates for common project structures:

#### 1. Monorepo (Multi-Package)
**When to use:** Single repo with multiple packages/services (e.g., backend, frontend, shared libs)

**Guide:** [docs/templates/monorepo.md](docs/templates/monorepo.md)
- Architecture: 3 agents (backend, frontend, test)
- Example config: [docs/examples/00-templates/monorepo-config.ini](docs/examples/00-templates/monorepo-config.ini)

#### 2. Microservices (Multi-Service)
**When to use:** Multiple services in separate repos that share a task DAG

**Guide:** [docs/templates/microservices.md](docs/templates/microservices.md)
- Architecture: Service-specific agents (auth, payment, inventory, etc.)
- Example config: [docs/examples/00-templates/microservices-config.ini](docs/examples/00-templates/microservices-config.ini)

#### 3. Single Service (Simple Parallel Work)
**When to use:** One service, one codebase, just want parallel task execution

**Guide:** [docs/templates/single-service.md](docs/templates/single-service.md)
- Architecture: Single agent, multiple parallel tasks
- Example config: [docs/examples/00-templates/single-service-config.ini](docs/examples/00-templates/single-service-config.ini)

### Configuration Decision Tree

```
Do you need custom agents?
│
├─ No → Use default (skip .village/config or use minimal config)
│
└─ Yes → Which structure?
    │
    ├─ Monorepo → See docs/templates/monorepo.md
    │
    ├─ Microservices → See docs/templates/microservices.md
    │
    └─ Single service → See docs/templates/single-service.md
        │
        └─ Then: Do you need PPC contracts?
            │
            ├─ No → Use default Markdown contracts
            │
            └─ Yes → Configure ppc_mode in .village/config
                (see custom-agent.md for details)
```

---

## Troubleshooting by Path

### Path A: Brand New Project — Common Issues

**Issue: "bd: command not found"**

**Fix:** Install Beads:
```bash
cargo install beads
```

**Issue: "tmux: command not found"**

**Fix:** Install tmux:
```bash
# macOS
brew install tmux

# Ubuntu/Debian
sudo apt-get install tmux
```

**Issue: "not in a git repository"**

**Fix:** Initialize Git:
```bash
cd /path/to/your/repo
git init
village up
```

**Issue: `village queue` shows "No tasks ready"**

**Fix:** Create tasks using Village's tools:
```bash
# Interactive creation
village add

# Or chat-based creation
village chat

# Verify Beads has ready tasks
bd ready
```

---

### Path B: Existing Project with Beads — Common Issues

**Issue: `village queue` starts 0 tasks**

**Possible causes:**
1. No ready tasks in Beads: Run `bd ready` to verify
2. All tasks are already claimed (ACTIVE locks): Run `village status --workers`
3. Concurrency limit reached: Run `VILLAGE_MAX_WORKERS=10 village queue`

**Fix:**
```bash
# Check ready tasks
bd ready

# Check existing workers
village status --workers

# Increase worker limit
VILLAGE_MAX_WORKERS=10 village queue --n 5
```

**Issue: "Lock already claimed" errors**

**Fix:** This is normal. Village skips tasks that are already running. Check `village status --workers` to see which tasks are claimed.

**Issue: Workers start but nothing happens**

**Possible causes:**
1. OpenCode not installed: Run `which opencode`
2. Beads task description is empty: Run `bd show <task-id>`
3. Agent contract is corrupted: Check `.village/config`

**Fix:**
```bash
# Verify OpenCode is installed
which opencode

# Check task details
bd show bd-a3f8

# Re-initialize Village if needed
village down
village up
```

---

### Path C: Existing Project with Village — Common Issues

**Issue: Stale locks after crash**

**Symptom:** `village status --workers` shows tasks that aren't running

**Fix:**
```bash
# Check for orphans
village status --orphans

# Clean up
village cleanup --apply
```

**Issue: Orphaned worktrees**

**Symptom:** `.worktrees/` directory has folders with no corresponding locks

**Fix:**
```bash
# Clean up orphans
village cleanup --apply

# Manual cleanup (if needed)
git worktree prune
```

**Issue: Corrupted lock files**

**Symptom:** `village status --locks` shows corrupted entries

**Fix:**
```bash
# View locks
village status --locks

# Force unlock specific task
village unlock bd-a3f8 --force

# Or cleanup with force
village cleanup --apply --force
```

---

## Version Notes

### v1.3+ — Jujutsu (jj) Support

If you're using Jujutsu (jj) instead of Git:

```ini
# .village/config
[DEFAULT]
SCM=jj
```

Or via environment variable:
```bash
SCM=jj village queue --n 3
```

All Village commands work identically with jj as with Git. No migration required.

---

## Next Steps

You've completed the quickstart! Here's what to explore next:

### For Customization
- [Custom Agent Guide](docs/examples/02-configuration/custom-agent.md) — Define specialized agents
- [Multiple Agents Guide](docs/examples/04-configuration/multiple-agents.md) — 3+ agents working together
- [Project Templates](#project-templates) — Pre-configured setups

### For Advanced Workflows
- [Queue Multiple Tasks](docs/examples/03-commands/queue-multiple.md) — Queue across agent types
- [Multi-Day Workflow](docs/examples/05-advanced/workflow.md) — Handle interrupts and recovery

### For Reference
- [Commands Reference](README.md#commands-reference) — All Village commands
- [Troubleshooting](README.md#troubleshooting) — Common issues and solutions
- [AGENTS.md](AGENTS.md) — Developer guidelines for contributing

---

## Need Help?

- **Documentation:** See [README.md](README.md) for complete reference
- **Examples:** See [docs/examples/](docs/examples/) for practical guides
- **Roadmap:** See [docs/ROADMAP.md](docs/ROADMAP.md) for future features
- **Issues:** Report bugs or request features on GitHub
