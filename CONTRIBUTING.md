# Contributing to Village

Village is intentionally small and opinionated.

---

## Core principles

1. No hidden state  
2. tmux is authoritative  
3. No daemon processes  
4. Safety over automation  
5. Readability beats cleverness  

---

## Out of scope

- background schedulers
- databases
- cloud dependencies
- YAML workflow DSLs

---

## Changelog

Village uses [Keep a Changelog](https://keepachangelog.com/) format.

Changes are automatically documented during release based on:
- Task type (bug → Fixed, feature → Added)
- Bump label (major → Breaking)

### For Contributors

When submitting changes:
1. Ensure task has clear, user-facing title
2. **Apply a bump label to every PR** (required — CI will block merges without one)
3. Changelog entries are generated automatically

No manual CHANGELOG.md edits needed.

#### Bump Labels

Every PR **must** have exactly one bump label:

| Label | When to use |
|-------|-------------|
| `bump:major` | Breaking changes, API removal |
| `bump:minor` | New features, backwards-compatible additions |
| `bump:patch` | Bug fixes, small improvements |
| `bump:none` | Docs, tests, internal refactors |

The label check runs automatically when a PR is opened, updated, or when labels
are added/removed. The PR cannot be merged until a bump label is present.
