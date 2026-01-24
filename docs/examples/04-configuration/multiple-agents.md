# Multiple Agent Configuration

This example shows how to configure and use multiple specialized agents.

## Use Case

You want to run a mixed workload:
- `build` agent - Backend services, conservative and terse
- `frontend` agent - UI components, verbose output
- `test` agent - Automated tests, dry-run first

## Agent Configuration

Create `.village/config` in your git repository:

```ini
[DEFAULT]
DEFAULT_AGENT=build

[agent.build]
opencode_args=--mode patch --safe --terse
contract=contracts/build.md
ppc_mode=build
ppc_traits=conservative,terse
ppc_format=markdown

[agent.frontend]
opencode_args=--mode patch --verbose
contract=contracts/frontend.md
ppc_mode=explore
ppc_traits=verbose
ppc_format=markdown

[agent.test]
opencode_args=--mode patch --dry-run
contract=contracts/test.md
ppc_mode=test
ppc_traits=terse
ppc_format=markdown
```

## Queue Mixed Workload

Queue all available tasks, respecting agent-specific configurations:

```bash
# Queue all ready tasks (mixed agents)
village queue --n 3
```

Expected output:
```
Starting 3 task(s)...

Tasks started: 3
Tasks failed: 0
```

## Inspect Active Workers

```bash
# See which agents are running
village status --workers
```

Expected output (with colors):
```
TASK_ID    STATUS    PANE     AGENT     WINDOW            CLAIMED_AT
bd-a3f8    ACTIVE    %12      build      build-1-bd-a3f8  12:34:56
bd-b7c2    ACTIVE    %13      frontend   frontend-1-bd-b7c2 12:34:58
bd-d9e3    ACTIVE    %14      test       test-1-bd-d9e3   12:35:01
```

## Resume with Specific Agent

```bash
# Resume a task with frontend agent (override default)
village resume bd-b7c2 --agent frontend
```

## Custom Contracts (Optional)

Create agent-specific contract templates:

**contracts/build.md:**
```markdown
# Build Agent Contract

## Mode: Build

Focus on:
- Correctness of changes
- Performance implications
- Following project conventions

## Constraints

- Always run tests before committing
- Use --mode patch for changes
- Prefer safe operations over risky refactors
```

**contracts/test.md:**
```markdown
# Test Agent Contract

## Mode: Test

Focus on:
- Test coverage
- Edge cases
- Reproducing reported issues

## Constraints

- Always use --dry-run first
- Run specific test files when possible
- Document test failures in commit messages
```

## Verify Agent Configuration

```bash
# Check that agents are loaded correctly
grep -A5 "\[agent.build\]" .village/config
```

Expected output from config file.

## Queue by Agent Type

```bash
# Queue only build agents
village queue --agent build --n 2

# Queue only frontend agents
village queue --agent frontend --n 2
```

## Next Steps

Try these examples:

1. [First Task](../01-quickstart/first-task.md) - Basic workflow without agents
2. [Custom Agent](../02-configuration/custom-agent.md) - Single agent setup
3. [Queue Multiple](../03-commands/queue-multiple.md) - Queue across agent types
4. [Multi-Day Workflow](../05-advanced/workflow.md) - Interrupt recovery and cleanup
