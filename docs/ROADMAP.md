# Village Roadmap

## Current Status: v2.1.0

> Village is a CLI-native parallel development orchestrator with audit trails, safety guarantees, and production reliability.

### Implemented Core Features (v0.2.3 - v2.1.0)

- [x] **v0.2.3**: SCM Abstraction
  - Git backend implementation
  - Pluggable SCM protocol
  - Zero git commands outside village/scm/git.py

- [x] **v0.3.0**: Safety & Coordination
  - State machine workflows (QUEUED → CLAIMED → IN_PROGRESS → PAUSED → COMPLETED → FAILED)
  - Automatic rollback on failure
  - Conflict detection

- [x] **v0.4.0**: Enhanced Observability
  - Real-time dashboard (`village dashboard`)
  - Metrics export (Prometheus, StatsD)
  - Structured event queries (`village events`)

- [x] **v1.0.0**: Production-Ready
  - Test coverage >85%
  - Zero critical bugs
  - Complete documentation

- [x] **v1.2.0**: Operational Reliability
  - Event logging (NDJSON)
  - Queue deduplication guard
  - Enhanced cleanup

- [x] **v1.4.0**: Memory System
  - File-based MemoryStore
  - Task description improvements

- [x] **v2.0.0**: Breaking Changes
  - Native task store
  - ACP (Agent Communication Protocol) integration
  - Role-based CLI (planner, builder, scribe, greeter, council, doctor)
  - Spec-driven build loop
  - Knowledge base system
  - Workflow engine
  - Adaptive onboarding
  - Extensibility framework

- [x] **v2.1.0**: Transport & Reliability
  - Unified transport architecture (PromptBridge, executor threads)
  - Progress streaming for long-running commands
  - Conversation memory persistence across ACP sessions
  - Project labels for multi-project task grouping
  - Builder waves and implicit landing
  - PR stacking infrastructure
  - Planner CRUD and builder arrange/rollback
  - Scribe auto-research for wiki gap-filling
  - Onboarding interview improvements
  - CI reliability and lint/type fixes

### Current Statistics

- **Total Python LOC**: ~6,000+
- **Test Coverage**: >85% overall
- **Commands Implemented**: 18+ subcommands across role-based CLI

---

## v2.2.0 - High-ROI Integrations (Planned)

### Goal
Automate high-value workflows that save significant time and improve team productivity.

### Scope

- [ ] **E2E Test Suite**
  - Comprehensive end-to-end testing (30+ tests)
  - Test classes: Onboarding, MultiTaskExecution, CrashRecovery, Concurrency, FullUserJourney

- [ ] **GitHub Integration**
  - PR description generator
  - PR status sync
  - CI/CD build triggers

- [ ] **Notification Systems**
  - Webhook support (Slack, Discord, Email)
  - Event-driven notifications

### Success Criteria

- [ ] E2E test suite passes
- [ ] GitHub PR automation works
- [ ] Notifications sent for configured events

---

## v2.3.0 - Medium-ROI Optimizations (Planned)

### Goal
Optimize throughput and user experience with medium-ROI features.

### Scope

- [ ] **Advanced Scheduling Policies**
  - Priority-based scheduling
  - Resource-aware scheduling
  - Fair-share scheduling
  - Dependency-aware scheduling

- [ ] **Multi-Repo Coordination**
  - Configuration per repo
  - Cross-repo task routing
  - Shared lock state

---

## v2.4.0 - Low-ROI Features (Planned)

### Goal
Add nice-to-have features for specific use cases.

### Scope

- [ ] **Resource Quotas**
  - CPU/memory/disk limits per agent
  - Pre-flight checks

- [ ] **Dynamic DAG Re-evaluation**
  - Runtime dependency resolution
  - Task status sync

---

## Definition of Done

Village should feel like:

> "a tiny operating system for parallel development."

Nothing hidden. Everything inspectable. Flow first.

---

## Implementation Timeline

| Version | Type | Status | Notes |
|---------|------|--------|-------|
| v0.2.3 | Release | ✅ Complete | SCM abstraction |
| v0.3.0 | Release | ✅ Complete | Safety & Coordination |
| v0.4.0 | Release | ✅ Complete | Enhanced Observability |
| v1.0.0 | Release | ✅ Complete | Production-Ready |
| v1.2.0 | Release | ✅ Complete | Operational Reliability |
| v1.4.0 | Release | ✅ Complete | Memory System |
| v2.0.0 | Release | ✅ Complete | ACP + Role CLI |
| v2.1.0 | Release | ✅ Complete | Transport & Reliability |
| v2.2.0 | Planned | 📅 Backlog | High-ROI Integrations |
| v2.3.0 | Planned | 📅 Backlog | Medium-ROI Optimizations |
| v2.4.0 | Planned | 📅 Backlog | Low-ROI Features |

---

## Contributing

See [AGENTS.md](../AGENTS.md) for development guidelines.

When implementing features from this roadmap:

1. Create a feature branch from main
2. Reference roadmap item in commit messages
3. Update this ROADMAP.md as you complete items
4. Ensure tests pass and coverage is maintained
5. Run linting: `uv run ruff check . && uv run mypy village/`
