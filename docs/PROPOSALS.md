# Village - Optional Extensions (Proposals)

## Status: Draft

This document defines where optional extensions provide clear value without compromising Village's core guarantees.

All features in this document are **optional** and **out of scope** for v1.0-v2.0.

---

## Core Principle

Village must remain in control of:
- Execution decisions
- Scheduling logic
- State mutations
- Arbitration between workers

Optional extensions may only:
- Generate text artifacts
- Provide context
- Enhance observability
- Automate non-critical workflows

Optional extensions must never:
- Make execution decisions
- Create implicit side effects
- Modify lock files
- Schedule work
- Mutate runtime state

---

## Fabric Integrations

Fabric is treated as an optional text-artifact backend, never as a decision engine.

### Tier 1 — Extremely High ROI

#### 1. `village chat` (Already Implemented)

**Status**: ✅ Complete in v0.1.0

Conversational interface for knowledge sharing and task creation.

**Value**:
- Faster project bootstrapping
- Explicit, durable shared understanding
- Human-in-the-loop alignment
- No execution side effects

**Safety**:
- All outputs are markdown files
- Never spawns agents or modifies runtime
- Read-only subcommands only
- Zero impact on runtime stability

#### 2. Agent Contract Generation via Fabric

**Status**: ❌ Not implemented

Automatically generate agent contracts using Fabric prompts.

**Proposal**:
```bash
village contract generate --agent frontend --task bd-a3f8
```

Outputs: `.village/contracts/bd-a3f8/frontend.md`

**Value**:
- Consistent contract quality
- Faster agent setup
- Less manual prompt engineering

**Safety**:
- File-backed output only
- No execution changes
- Human must review before use
- Can be overridden with custom contracts

**Integration Points**:
- Hook into existing `village contracts` module
- Use Fabric's summarization/extraction patterns
- Cache generated contracts for reuse

### Tier 2 — High ROI

#### 3. Task Drafting (Human-Approved)

**Status**: ⚠️ Partially implemented in `village/chat/drafts.py`

Assist humans in defining structured tasks for Beads.

**Proposal**:
```bash
village chat --create
> /draft "Add Redis caching to authentication layer"
> [Fabric analyzes codebase, asks clarifying questions]
> [Human refines scope, success criteria, dependencies]
> /submit
```

**Value**:
- Faster task creation workflow
- Better task quality (scope, success criteria)
- Consistent Beads task format
- Human remains in control

**Safety**:
- Never auto-submits to Beads
- Always requires human approval
- Drafts stored in `.village/drafts/`
- Can be edited/discarded before submission

**Current Status**:
- Draft system exists in `village/chat/drafts.py`
- Missing: Fabric-powered analysis and suggestions
- Missing: Codebase context injection

#### 4. Project Summary / Digest

**Status**: ❌ Not implemented

Generate project summaries and documentation from conversation history.

**Proposal**:
```bash
village chat --digest
> [Fabric reviews conversation history]
> [Generates project overview, blockers, decisions]
> [Writes to .village/context/summary.md]
```

**Value**:
- Automatic documentation updates
- Onboarding for new developers
- Project health overview
- Decision trail capture

**Safety**:
- File-backed output only
- Review before commit
- Can be versioned in git

### Tier 3 — Medium ROI

#### 5. PR Description Generator

**Status**: ❌ Not implemented

Generate pull request descriptions from Beads task data and git diff.

**Proposal**:
```bash
village pr describe bd-a3f8
> [Fabric extracts task metadata]
> [Fabric analyzes git changes]
> [Generates PR description with testing checklist]
```

**Value**:
- Consistent PR quality
- Faster PR submission
- Automatic testing checklist
- Links back to Beads tasks

**Safety**:
- Outputs to stdout or file
- Human must paste into PR form
- No direct GitHub API access
- Can be regenerated

#### 6. Release Notes Generation

**Status**: ❌ Not implemented

Generate release notes from completed Beads tasks.

**Proposal**:
```bash
village release notes v1.0.0 v0.9.0
> [Fabric extracts completed tasks in range]
> [Fabric groups by type/impact]
> [Generates markdown release notes]
```

**Value**:
- Consistent release notes format
- Faster release preparation
- Links to tasks and changes
- Categorization (features, fixes, breaking changes)

**Safety**:
- Outputs to stdout or file
- Human review before publishing
- No direct release management
- Idempotent (re-run safely)

---

## Enhanced Observability

### Metrics Export

**Status**: ❌ Not implemented

Export Village metrics to observability backends.

**Proposal**:
```bash
village metrics export --backend prometheus
village metrics export --backend statsd
```

**Metrics**:
- Active workers count
- Queue length (ready, blocked)
- Stale lock count
- Task completion rate
- Average task duration

**Value**:
- Production monitoring
- Capacity planning
- Trend analysis
- Alerting on anomalies

**Safety**:
- Read-only export
- No performance impact (async)
- Optional feature (off by default)
- No storage requirements in Village

### Real-Time Dashboards

**Status**: ❌ Not implemented

Live dashboard showing Village state in real-time.

**Proposal**:
```bash
village dashboard --watch
```

**Features**:
- Active workers table
- Task queue visualization
- Lock status (ACTIVE/STALE)
- Orphan detection alerts
- Historical task completion graph

**Value**:
- Better situational awareness
- Faster debugging
- Visual state inspection
- No need to run `village status` repeatedly

**Safety**:
- Read-only view
- No state mutations
- Optional feature
- No dependencies on external services

---

## Advanced Workflows

### Multi-Repo Support

**Status**: ❌ Not implemented

Coordinate tasks across multiple git repositories.

**Proposal**:
```ini
[repo.backend]
path=../backend
agent=backend-build

[repo.frontend]
path=../frontend
agent=frontend-build

village queue --repo backend --n 3
village queue --repo frontend --n 2
```

**Value**:
- Microservices orchestration
- Cross-repo dependencies
- Unified task view
- Parallel multi-repo execution

**Challenges**:
- Complex dependency management
- Worktree isolation across repos
- Beads task routing to correct repo
- Increased complexity

### Remote Tmux Sessions

**Status**: ❌ Not implemented

Support remote tmux sessions over SSH.

**Proposal**:
```bash
village up --session=user@server:village
village queue --session=user@server:village
```

**Value**:
- Remote development
- Resource scaling
- Team coordination
- Distributed task execution

**Challenges**:
- SSH key management
- Network reliability
- File system access (worktrees)
- Security considerations

**Note**: This is explicitly non-goal for v1-v2. Consider only if strong user demand exists.

### Custom Scheduler Policies

**Status**: ❌ Not implemented

Allow users to define custom scheduling policies.

**Proposal**:
```python
# .village/scheduler.py
def should_schedule(task, active_workers, system_state):
    # Example: prioritize high-impact tasks
    if task.metadata.get("impact") == "high":
        return True, "high priority"
    return default_policy(task, active_workers, system_state)
```

**Value**:
- Team-specific workflows
- Custom prioritization logic
- Flexible resource allocation
- Extensible without core changes

**Safety**:
- Policy is opt-in
- Village still controls execution
- Fail-safe fallback to default
- Type-checked policies

---

## Safety Rules for All Proposals

When implementing any proposal in this document, these rules must be followed:

1. **No execution decisions**
   - Proposals cannot decide what runs
   - Village must remain the scheduler
   - Proposals may only suggest or generate

2. **No implicit side effects**
   - All outputs must be explicit
   - No hidden file mutations
   - No lock file modifications
   - No runtime state changes

3. **File-backed outputs only**
   - Text artifacts are okay
   - Markdown files are preferred
   - Must be version-controlled
   - Human must review

4. **Explicit invocation required**
   - No automatic background processes
   - User must type commands
   - Opt-in features only
   - Clear scope boundaries

5. **Village guarantees remain**
   - Local-first
   - File-based
   - Inspectable
   - Safe by default
   - No magic

---

## Proposal Evaluation Criteria

When considering new proposals:

1. **ROI Alignment**
   - Does it solve real user pain?
   - Is the implementation cost justified?
   - Can it be done simply?

2. **Safety Guarantee**
   - Can it violate Village's core principles?
   - Does it introduce hidden state?
   - Is it transparent and inspectable?

3. **Optional Nature**
   - Can Village work without it?
   - Is it opt-in?
   - Does it increase complexity for non-users?

4. **Maintainability**
   - Does it bloat the codebase?
   - Is it well-scoped?
   - Can it be tested independently?

5. **User Control**
   - Does the human remain in control?
   - Can outputs be reviewed/edited?
   - Is invocation explicit?

---

## Summary

Village's core value is safe, transparent, local-first coordination. Optional extensions may enhance productivity but must never compromise the core guarantees:

- Village remains the scheduler
- Humans remain in control
- State remains file-based and inspectable
- No magic, no hidden processes, no side effects

When in doubt, keep it simple. A small, reliable tool is better than a complex, feature-rich one.
