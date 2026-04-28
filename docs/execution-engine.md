# Execution Engine

The execution engine ensures AI agent actions follow declared policies and cannot be
circumvented, regardless of the agent or harness being used.

## Architecture

```
Agent proposes actions → Engine validates → Engine executes approved → Agent observes results
```

The engine is the policy enforcement layer that sits between AI agents and the filesystem.
It classifies actions into security tiers, validates them against rules and manifests,
and optionally executes them with resource limits and a sanitized environment.

## Four-Layer Defense

The execution engine operates at four distinct layers of the development pipeline:

### Layer 1: Contract integration (agent instructions)

PPC (Process Protection Contract) guardrail modules describe behavioral constraints in
the agent's system prompt. Agents are told the rules before they start working. This
is the first line of defense — making expectations explicit before any action occurs.

### Layer 2: Execution engine (runtime validation)

All agent actions must go through the execution engine as structured `<plan>` proposals.
The engine:

1. **Classifies** each action into a security tier
2. **Validates** against configured rules and manifests
3. **Executes** with resource limits and sanitized environment (if approved)
4. **Scans** the result for content violations

This is the primary runtime defense layer.

### Layer 3: Post-hoc verification (completion gate)

After the agent signals DONE (`<promise>DONE</promise>`), the engine runs final checks
before marking the spec complete:

- **Content scanning** — no forbidden patterns in new/modified files
- **Filename casing** — new files match configured casing
- **TDD enforcement** — test files exist for new source files

If verification fails, violations are written as "Inspect Notes" in the spec file so
the agent can fix them on retry.

### Layer 4: Remote CI (push-time enforcement)

Optional CI workflows validate that each role's commits only touch allowed paths and
respect project policies. This is an additional safety net at push time.

## Tier Classification

| Tier | Name | Auto-approve? | Examples |
|------|------|---------------|----------|
| 0 | READ_ONLY | Yes | `cat`, `ls`, `grep`, `git log`, `git diff`, `git status` |
| 1 | SAFE_WRITE | Yes | `mkdir`, `pytest`, `ruff format`, `touch`, `cp`, `mv` |
| 2 | DESTRUCTIVE | Only if in manifest | `rm file`, `git reset`, `pip install`, `git push` (no --force) |
| 3 | DANGEROUS | Never | `rm -rf`, `git push --force`, `chmod 777`, `sudo`, `chown` |

### Classification details

- **Executable resolution**: Path prefixes are stripped (`/bin/rm` → `rm`) for
  canonical lookup.
- **Git subcommands**: `git log/diff/status` → Tier 0; `git add/commit` → Tier 1;
  `git reset/push` → Tier 2; `git push --force` → Tier 3.
- **Docker subcommands**: `docker ps/images` → Tier 0; `docker build/pull` → Tier 2;
  `docker run/exec` → Tier 3.
- **Shell metacharacters**: Any command containing `$()`, backticks, `&&`, `||`, or `;`
  is elevated to at least Tier 2.
- **Pipe-to-shell**: Any command piping to `sh`, `bash`, `zsh`, etc. is elevated to
  Tier 3.

## Attack Vector Protection

| # | Vector | Protection |
|---|--------|------------|
| 1 | Config tampering | Builder reads from frozen git commit, not filesystem |
| 2 | Script injection | Content scanner blocks dangerous patterns (`subprocess.run`, `os.system`, `eval`, `exec`) |
| 3 | Shell metacharacters | `shlex`-based parsing blocks `$()`, `` ` ``, `&&`, `\|\|`, `;` |
| 4 | Symlink escape | `Path.resolve()` before boundary checks; raises `ValueError` on escape |
| 5 | Race conditions | Commit-time validation + `hash-object` snapshot (reads from disk at commit moment) |
| 6 | Environment injection | Sanitized environment per command — strips `SSH_AUTH_SOCK`, `PYTHONPATH`, `LD_PRELOAD`, `GIT_DIR` |
| 7 | Nested repo bypass | `git clone` is classified as at least Tier 2 (DESTRUCTIVE) |
| 8 | Resource exhaustion | `setrlimit`: CPU, memory, file size, number of processes + wall-clock timeout |

## Modules

The execution engine is composed of these modules:

| Module | Class | Purpose |
|--------|-------|---------|
| `tiers.py` | `TierClassifier` | Classifies bash commands and file writes into security tiers |
| `validator.py` | `CommandValidator` | Validates classified actions against rules and manifests |
| `scanner.py` | `ContentScanner` | Scans file contents, filenames, and TDD compliance |
| `commit.py` | `CommitEngine` | Sole committer — creates tamper-proof commits using low-level git plumbing |
| `env.py` | `EnvironmentSanitizer` | Builds a minimal, predictable execution environment |
| `paths.py` | `PathPolicy` | Path-based access control with symlink escape detection |
| `resources.py` | `ResourceGuard` | OS-level resource enforcement (CPU, memory, processes, timeout) |
| `refs.py` | `freeze_build_commit`, `git_show` | Config freezing and tamper-proof reads from git objects |
| `manifest.py` | `ManifestStore`, `ApprovalManifest` | Per-spec approval manifests loaded from git |
| `verify.py` | `run_verification` | Post-hoc verification after agent signals completion |
| `protocol.py` | `PlanProtocol` | `<plan>`/`<executed>` protocol between agent and engine |
| `engine.py` | `ExecutionEngine` | Top-level pipeline: classify → validate → execute → scan |

## Configuration

### `.village/rules.yaml`

Global policy rules loaded at build start. Read from the frozen git commit for
tamper-proofing. Supports:

- **`content_rules`**: Forbidden patterns (literal or regex) with optional path scoping
- **`command_rules`**: Forbidden commands with flag, subcommand, and pipe-to checks
- **`filename`**: Casing enforcement (`snake_case`, `kebab-case`, `camelCase`)
- **`tdd`**: Test-driven development enforcement

### `.village/agents.yaml`

Per-role git identities and allowed paths. Each role maps to a specific git user/email
and set of allowed path patterns.

### `.village/approvals/<spec-id>.yaml`

Per-spec command and script whitelists. Read from git objects (tamper-proof) — the
builder never reads these from disk during a build.

Structure:
```yaml
version: 1
spec_id: my-feature
allowed_commands:
  - pytest
  - ruff
  - git add
allowed_scripts:
  - build.py
allowed_paths:
  - src/**
  - tests/**
test_required: true
filename_casing: snake_case
```

## Protocol

Agents communicate with the execution engine using `<plan>`/`<executed>` markers:

### Proposal

The agent outputs a structured JSON plan:

```
<plan>
[
  {"action": "write", "path": "src/foo.py", "content": "print('hello')"},
  {"action": "bash", "command": "pytest tests/test_foo.py -v"}
]
</plan>
```

### Execution

The engine:
1. Parses the `<plan>` block
2. Classifies each action into a security tier
3. Validates against rules and manifests
4. Executes approved actions with resource limits
5. Returns results

### Response

The engine sends back structured results:

```
<executed>
[
  {"id": 0, "status": "ok"},
  {"id": 1, "status": "ok", "stdout": "1 passed in 0.5s"}
]
</executed>
```

The agent reads the results and continues. This repeats until the spec is complete.

### Supported action types

- **`write`**: Write content to a file (`path` + `content`)
- **`bash`**: Execute a command (`command` string)
- **`delete`**: Delete a file (`path`)
- **`read`**: Read a file (`path`) — auto-approved

## Key Design Decisions

### Git plumbing for commits

The `CommitEngine` uses low-level git commands (`hash-object`, `update-index`,
`write-tree`, `commit-tree`) instead of `git add`/`git commit`. This prevents race
conditions where an agent modifies a file between validation and commit — each file's
content is hashed at the exact moment of commit.

### Frozen config reads

At the start of each build, `freeze_build_commit()` captures the current HEAD commit
hash. All config reads during the build use `git_show()` to read from that commit
object — never from the filesystem. This makes config files tamper-proof: an agent
can write anything to `.village/rules.yaml` on disk, but the builder always reads the
original approved version from git.

### Sanitized environment

Every agent command executes in a minimal environment built from scratch. Known-dangerous
variables (`SSH_AUTH_SOCK`, `PYTHONPATH`, `LD_PRELOAD`, `GIT_DIR`) are stripped.
Environment injection is prevented because the parent process's environment is never
inherited directly.

### Resource limits

OS-level resource limits (`setrlimit`) are applied to every subprocess:
- **CPU time**: 5 minutes (soft limit)
- **Memory**: 4 GB (address space)
- **File size**: 1 GB
- **Processes**: 100 (prevents fork bombs)
- **Wall clock**: 1 hour (subprocess timeout)

These prevent resource exhaustion attacks from runaway agent commands.

## Example: Full Pipeline

```python
from pathlib import Path
from village.execution import ExecutionEngine
from village.execution.manifest import ManifestStore
from village.execution.refs import freeze_build_commit, git_show
from village.rules.loader import load_rules
from village.rules.schema import RulesConfig

# 1. Freeze config at build start
build_commit = freeze_build_commit(Path("/path/to/repo"))

# 2. Load rules from frozen commit (not filesystem!)
rules = load_rules(Path("/path/to/repo"), build_commit)

# 3. Create engine
engine = ExecutionEngine(rules=rules, worktree=Path("/path/to/repo"))

# 4. Agent proposes an action
action = {"type": "bash", "command": "pytest tests/"}

# 5. Load manifest from git (tamper-proof)
store = ManifestStore(Path("/path/to/repo/.village/approvals"))
manifest = store.load_from_git("my-spec", build_commit)

# 6. Execute through pipeline
result = engine.execute(
    worktree=Path("/path/to/repo"),
    action=action,
    manifest=manifest,
)
print(f"Status: {result.status}")
print(f"Stdout: {result.stdout[:500]}")
```
