# Implicit PR Stacking

Status: incomplete

## Problem

Large changes are difficult to review. Monolithic PRs slow down feedback loops,
reduce review quality, and create merge conflicts. Existing stacking tools
(`ghstack`, `gh stack`, Graphite) are external, VCS-specific, and require
explicit user knowledge of stacking concepts.

Village already decomposes work into tasks with hierarchical relationships.
This structure should drive PR creation automatically, eliminating the need
for users to understand stacking as a separate concept.

## Solution

PR stacking becomes an **implicit mechanic** driven by task labels. The
autonomous landing workflow creates stacked PRs automatically when all tasks
in a plan are completed. Users opt *out* of stacking with `--flat`, not *into*
it.

The existing `village release` command is removed. Landing happens implicitly
when the last task completes.

## Autonomous Landing Lifecycle

```
1. CHART COURSE
   village planner design <objective>
   → Planner decomposes objective into tasks via sequential thinking MCP
   → Auto-generates slug ID from objective (user can override with --name)
   → Initial stack labels proposed: stack:layer:N, stack:group:<name>
   → Plan stored as draft in .village/plans/drafts/<slug>/

2. COURSE SEALED
   village planner approve <slug>
   → Plan locked (immutable decomposition, mutable labels)
   → Worktree created for the plan
   → Development begins

3. DEVELOPMENT
   → Builder implements tasks via Ralph Wiggum loop
   → Labels evolve through waves (refined as implementation progresses)
   → Waves triggered each time a task reaches DONE
   → Agents own label evolution; users review/accept/reject
   → If rejected: agent proposes alternative or throws cant-continue error

4. DEVELOPMENT CANCELLED?
   ├─ YES → village rollback [--save|--purge]
   │   ├─ --save (default): preserve worktree, mark plan as "aborted"
   │   └─ --purge: delete worktree entirely
   └─ NO  → continue

5. LANDING (IMPLICIT)
   → Triggered when all tasks in the plan reach DONE
   → Builder reads final task labels
   → Tasks grouped by stack:group
   → Groups ordered by stack:layer
   → PRs created (one per group)
   → PRs arranged as a stack (each targets the branch of the layer below)
   → Changes pushed to trunk
```

## Label Taxonomy

Stack labels are freeform strings in the existing `task.labels: list[str]`
field. No schema changes required.

### Stack Labels

| Label | Meaning | Example |
|-------|---------|---------|
| `stack:layer:1` | Closest to trunk (foundational) | Core types, interfaces |
| `stack:layer:2` | Depends on layer 1 | Implementations |
| `stack:layer:N` | Depends on layers below | Higher-level features |
| `stack:group:<name>` | Logical grouping | `stack:group:auth`, `stack:group:api` |
| `stack:flat` | Force monolithic PR (escape hatch) | Small changes, hotfixes |

### Existing Labels (unchanged)

| Label | Meaning |
|-------|---------|
| `bump:major` | Breaking change |
| `bump:minor` | New feature |
| `bump:patch` | Bug fix |
| `bump:none` | No version impact |

### Label Resolution Rules

1. Tasks in the same `stack:group` become a single PR
2. Groups are ordered by `stack:layer` (ascending)
3. If no `stack:group` is set, each task becomes its own PR
4. If `stack:flat` is set on ANY task in the plan, the entire plan lands as one PR
5. Layer collisions within a group are resolved by max layer value

## Wave-Based Label Evolution

Labels are not static. They evolve as implementation progresses.

### Wave Trigger

A wave is triggered every time a task transitions to `DONE`. The wave:

1. Examines all tasks in the current plan
2. Uses sequential thinking MCP (like task decomposition) to evaluate:
   - Are groupings still logical given implemented code?
   - Should layers be adjusted based on discovered dependencies?
   - Are new groupings needed for tasks that grew in scope?
3. Proposes label updates
4. Presents updates to user for review (accept/reject with reason)

### Wave Constraints

- Waves NEVER change task decomposition (locked at approval)
- Waves ONLY modify stack:* labels
- If user rejects, agent must propose alternative or throw `cant-continue`
- Waves are bounded: at most N proposals per wave (configurable, default 3)

## Plan Storage

```
.village/plans/
├── drafts/
│   └── <slug>/
│       ├── plan.json          # Plan metadata, objective, created_at
│       ├── tasks.jsonl        # Draft tasks (pre-approval)
│       ├── interview.jsonl    # Reverse-prompting session history
│       └── labels.json        # Current label proposals
└── approved/
    └── <slug>/
        ├── plan.json          # Plan metadata (status: approved)
        ├── tasks.jsonl        # Finalized task decomposition
        ├── labels.json        # Final label state
        └── worktree           # Symlink or reference to .worktrees/<slug>/
```

### Plan States

| State | Location | Meaning |
|-------|----------|---------|
| `draft` | `.village/plans/drafts/<slug>/` | Pending user approval |
| `approved` | `.village/plans/approved/<slug>/` | Development in progress |
| `landed` | `.village/plans/approved/<slug>/` | All tasks done, PRs merged |
| `aborted` | `.village/plans/approved/<slug>/` | Rolled back (--save) |
| `purged` | (deleted) | Rolled back (--purge) |

### Slug Generation

- Auto-generated from objective text: `auth-overhaul` from "Overhaul the authentication system"
- Deterministic: same objective produces same slug
- On collision: error at startup (`error: name "auth-overhaul" already exists`)
- User override: `--name <slug>` flag

## VCS Abstraction

Stack operations are VCS-agnostic. A `StackBackend` abstracts the underlying
VCS (Git or Jujutsu).

### Interface

```python
class StackBackend(ABC):
    @abstractmethod
    def create_branch(self, name: str, base: str) -> str:
        """Create a branch at base. Return branch ref."""

    @abstractmethod
    def push_branch(self, name: str, remote: str = "origin") -> None:
        """Push branch to remote."""

    @abstractmethod
    def create_pr(self, head: str, base: str, title: str, body: str, draft: bool = False) -> str:
        """Create a pull request. Return PR URL."""

    @abstractmethod
    def rebase_onto(self, branch: str, new_base: str) -> None:
        """Rebase branch onto new base."""

    @abstractmethod
    def merge_pr(self, pr_ref: str) -> None:
        """Merge a pull request."""

    @abstractmethod
    def get_current_branch(self) -> str:
        """Return current branch name."""

    @abstractmethod
    def list_commits(self, base: str, head: str) -> list[str]:
        """List commit hashes between base and head."""
```

### Implementations

| VCS | Module | Key Differences |
|-----|--------|----------------|
| Git | `village/stack/git_backend.py` | Branches, rebase, force-push |
| JJ | `village/stack/jj_backend.py` | `jj evolve` for rebasing, workspaces |

## Abort Mechanism

When a user triggers rollback (from interactive session or CLI):

1. Write `.village/plans/<slug>/abort` signal file
2. Worker panes periodically check for this file (every 60s)
3. On detection: workers gracefully stop (save state, close tasks)
4. If graceful fails after 30s: `tmux kill-pane` as fallback
5. Handle worktree based on `--save` (preserve) or `--purge` (delete)

## CLI Commands

### New Commands

```bash
# Planner (existing group, new subcommands)
village planner design <objective>           # Create draft (auto-slug or --name)
village planner list [--all|--drafts|--pending|--completed|--aborted]
village planner show <slug>                   # Inspect a plan
village planner resume <slug>                # Interactive reverse-prompting session
village planner approve <slug>               # Seal plan, create worktree, start dev
village planner delete <slug> [--force]      # Delete draft (--force for non-drafts)

# Builder (existing group, new subcommands)
village builder arrange                      # Read labels, group tasks, create stacked PRs
village builder rollback [--save|--purge]   # Abort current plan, rollback worktree
```

### Removed Commands

```bash
village release                              # REMOVED — landing is implicit
village builder release                      # REMOVED — absorbed into arrange + implicit landing
```

### Startup Warnings

When `village planner design` is invoked and drafts exist:
```
warning: 3 drafts pending approval
```

### Slug Auto-Complete (Future)

Tab completion for plan slugs. Nice-to-have, not in initial implementation.
Will use Click's built-in shell complete or `argcomplete`.

## Acceptance Criteria

1. `village planner design "objective"` creates a draft with auto-generated slug
2. `village planner approve <slug>` seals the plan and creates a worktree
3. Builder implements tasks via existing Ralph Wiggum loop
4. Labels evolve through waves (triggered on task DONE)
5. When all tasks complete, `builder arrange` groups tasks into stacked PRs
6. PRs are created automatically with correct base branches
7. `--flat` flag produces a single monolithic PR
8. `village rollback --save` preserves worktree, marks plan aborted
9. `village rollback --purge` deletes worktree entirely
10. `village planner delete <slug>` removes drafts (--force for non-drafts)
11. VCS abstraction supports both Git and Jujutsu
12. Startup warning shown when drafts are pending

## Out of Scope

- Partial landings (too complex with worktree isolation)
- Draft expiration (never implicit)
- Slug auto-complete (future nice-to-have)
- Cross-fork stacking
- Reordering layers after approval
- Parallel building (existing `-p` flag, not stacking-related)

## Dependencies

- Sequential thinking MCP (already used for task decomposition)
- Existing task store (`.village/tasks.jsonl`)
- Existing label system (`task.labels: list[str]`)
- tmux for worker isolation (already in use)
- Git worktrees (already in use)
- JJ support (new, requires `jj` binary)

## Files to Create

```
village/stack/
├── __init__.py              # Package init
├── core.py                  # Stack, Layer, StackPlan dataclasses
├── backend.py               # StackBackend ABC
├── git_backend.py           # GitStackBackend implementation
├── jj_backend.py            # JJStackBackend implementation (stub)
├── arrange.py               # builder arrange logic (group, order, create PRs)
├── labels.py                # Label taxonomy, parsing, resolution
├── waves.py                 # Wave-based label evolution
├── abort.py                 # Abort signal handling
└── slug.py                  # Slug generation from objective text

village/plans/
├── __init__.py              # Package init
├── store.py                 # PlanStore (CRUD for plans)
├── models.py                # Plan, PlanState dataclasses
├── interview.py             # Reverse-prompting session logic
└── decomposition.py         # LLM-driven task decomposition from objective
```

## Files to Modify

```
village/cli/planner.py       # Add list, show, resume, approve, delete commands
village/cli/builder.py       # Add arrange, rollback commands; remove release command
village/cli/release.py       # REMOVED
village/roles.py             # Update routing table if needed
village/loop.py              # Integrate wave triggers on task completion
village/release.py           # Absorb version/changelog logic into arrange
```

## Migration Notes

- Existing `village release` users will need to use `village builder arrange`
- Existing bump labels (`bump:*`) continue to work unchanged
- Version computation and changelog generation are preserved in arrange
- Existing task store format is unchanged (labels are already freeform strings)
