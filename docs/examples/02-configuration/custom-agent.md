# Custom Agent Configuration

This example shows how to define a custom agent with specialized behavior.

## Use Case

You want a "review" agent that:
- Uses safe mode patches
- Generates code with verbose output
- Doesn't make changes (--dry-run first)

## Custom Agent Configuration

Create `.village/config` in your git repository:

```ini
[DEFAULT]
DEFAULT_AGENT=worker

[agent.review]
opencode_args=--mode patch --safe --dry-run
contract=contracts/review.md
ppc_mode=explore
ppc_traits=verbose,terse
ppc_format=markdown
```

## Custom Contract (Optional)

Create `contracts/review.md` with custom instructions:

```markdown
# Code Review Task: {task_id}

## Goal
Review the code changes in this worktree for:
- Correctness and logic errors
- Performance concerns
- Security vulnerabilities
- Style and maintainability

## Instructions

1. Start by reading the task description in `bd show {task_id}`
2. Review all modified files: `git diff HEAD~1`
3. Add inline comments for issues found
4. Use conservative suggestions (prefer safe fixes over refactors)

## Output

After reviewing, create a review summary in the task log.

## Context
- Worktree: {worktree_path}
- Git root: {git_root}
- Created: {created_at}
```

## Using the Custom Agent

```bash
# Queue a task with the review agent
village queue --agent review --n 1

# Or resume a specific task with the review agent
village resume bd-a3f8 --agent review
```

## Verification

```bash
# Check if agent config is loaded
village status --workers
```

Expected output shows the `review` agent for queued tasks.

## Multiple Custom Agents

You can define multiple specialized agents:

```ini
[agent.security]
opencode_args=--mode patch --safe
ppc_mode=explore
ppc_traits=terse
ppc_format=markdown

[agent.refactor]
opencode_args=--mode refactor --dry-run
ppc_mode=build
ppc_traits=verbose
ppc_format=markdown

[agent.docs]
opencode_args=--mode patch
contract=contracts/documentation.md
ppc_mode=explore
ppc_traits=verbose
```

## Next Steps

Try these examples:

1. [Multiple Agents](../04-configuration/multiple-agents.md) - Use several specialized agents together
2. [Queue Multiple](../03-commands/queue-multiple.md) - Queue tasks across different agent types
