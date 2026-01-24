# Village v1.1 PRD — SCM-Abstraction Edition

## Purpose

Village is a local-first parallel development orchestrator designed to safely coordinate
multiple AI agents working concurrently.

Version v1.1 formalizes a critical architectural boundary:

Village must not depend directly on Git semantics.

Instead, Village operates against a minimal SCM abstraction layer, allowing:

- Git worktrees in v1
- painless Jujutsu (jj) support in v2
- zero refactoring of core scheduling logic

---

## Design Goals

- Preserve all v1 behavior
- Introduce SCM modularization
- Avoid dual-backend complexity
- Enable jj transition without migration pain
- Keep codebase small (< 2k LOC)

---

## SCM Interface

```
class SCM(Protocol):
    kind: Literal["git", "jj"]

    def ensure_repo(repo_root: Path) -> None
    def ensure_workspace(repo_root: Path, ws: Workspace, base_ref: str = "HEAD") -> None
    def list_workspaces(repo_root: Path, worktrees_dir: Path) -> list[Workspace]
```

---

## Workspace Model

.worktrees/bd-a3f8-build-auth/

- directory name encodes task ID
- directory is authoritative identity
- SCM metadata irrelevant to Village

---

## Git Backend

- uses git worktree add
- per-task branches: task/<id>
- idempotent behavior
- branch names never leak outside SCM

---

## Configuration

SCM=git
WORKTREES_DIR=.worktrees
SESSION=village

---

## Success Criteria

- zero git calls outside village/scm
- core logic SCM-agnostic
- jj backend possible without refactor
