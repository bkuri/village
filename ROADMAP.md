# Village --- Implementation Roadmap (Updated)

## Phase 0 --- Freeze Bash Reference

-   [ ] Lock current bash behavior
-   [ ] Treat as executable spec
-   [ ] No new features added there

------------------------------------------------------------------------

## Phase 1 --- Python Skeleton

-   [ ] pyproject.toml (uv-native)
-   [ ] CLI entrypoint
-   [ ] config loader
-   [ ] subprocess wrapper
-   [ ] logging helpers

Deliverable: - `village status --short`

------------------------------------------------------------------------

## Phase 2 --- Runtime Probes

-   [ ] tmux session detection
-   [ ] pane enumeration
-   [ ] pane existence cache
-   [ ] beads availability detection

Deliverable: - reliable probe layer

------------------------------------------------------------------------

## Phase 3 --- Lock System

-   [ ] Lock dataclass
-   [ ] parse/write helpers
-   [ ] ACTIVE / STALE evaluation
-   [ ] unlock safety logic

Deliverable: - `village locks` - `village cleanup --dry-run`

------------------------------------------------------------------------

## Phase 4 --- Status System

-   [ ] workers view
-   [ ] orphans detection
-   [ ] short renderer
-   [ ] json renderer

Deliverable: - full `village status` parity

------------------------------------------------------------------------

## Phase 5 --- Ready Engine

-   [ ] readiness decision tree
-   [ ] suggested actions engine
-   [ ] json schema enforcement
-   [ ] text renderer

Deliverable: - `village ready`

------------------------------------------------------------------------

## Phase 6 --- Runtime Lifecycle

-   [x] `village up`
-   [x] `village down`
-   [x] dry-run support
-   [x] dashboard creation

Deliverable: - deterministic runtime management

------------------------------------------------------------------------

## Phase 7 --- Resume Flow

-   [ ] resume `<id>`{=html}
-   [ ] resume (no id) planner
-   [ ] --apply execution path
-   [ ] detached mode

Deliverable: - unified resume semantics

------------------------------------------------------------------------

## Phase 8 --- Queue Scheduler

-   [ ] ready extraction
-   [ ] lock arbitration
-   [ ] auto naming
-   [ ] concurrency limits
-   [ ] plan mode

Deliverable: - `village queue`

------------------------------------------------------------------------

## Phase 9 --- Contracts

-   [ ] ppc detection
-   [ ] agent → args mapping
-   [ ] fallback contracts
-   [ ] injection formatting

Deliverable: - behavior parity with bash

------------------------------------------------------------------------

## Phase 10 --- Hardening

-   [ ] error classification
-   [ ] exit codes
-   [ ] interrupted execution recovery
-   [ ] corrupted lock handling

------------------------------------------------------------------------

## Phase 11 --- Polish

-   [ ] colored TTY output
-   [ ] shell completion
-   [ ] README
-   [ ] examples
-   [ ] migration notes

------------------------------------------------------------------------

## Explicitly Out of Scope

-   daemon mode
-   distributed workers
-   remote tmux
-   stateful scheduler loop

------------------------------------------------------------------------

## Definition of Done

Village should feel like:

> "a tiny operating system for parallel development."

Nothing hidden. Everything inspectable. Flow first.
