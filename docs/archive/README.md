# DEPRECATED — Archived Documents

> **DEPRECATED** — These documents are out of date. See the current documentation in the parent `docs/` directory.

This directory contains older PRD, roadmap, and design documents that have been consolidated or superseded.

## Consolidation Notes

As of January 24, 2026, the following documents have been consolidated:

### PRDs
- **VILLAGE_PRD_v1.1.md** → Merged into [../ROADMAP.md](../ROADMAP.md)
- **VILLAGE_PRD_v1.2.md** → Merged into [../ROADMAP.md](../ROADMAP.md)
- **VILLAGE_PRD_v2_DRAFT.md** → Merged into [../ROADMAP.md](../ROADMAP.md)
- **VILLAGE_FABRIC_INTEGRATIONS_PRD.md** → Merged into [../PROPOSALS.md](../PROPOSALS.md)

### Roadmaps
- **VILLAGE_ROADMAP_v1.1.md** → Replaced by [../ROADMAP.md](../ROADMAP.md)

### Chat Design Documents (archived April 2026)
- **CHAT_HELP.md** — Slash command reference for `village chat`; superseded by inline help
- **PPC_POLICY_village-chat.md** — LLM policy for knowledge-sharing mode; superseded by embedded prompts
- **VILLAGE_CHAT_PRD.md** — Product requirements for `village chat`; design finalized and shipped
- **WORKFLOW_EXAMPLES.md** — Workflow examples for `village chat`; content folded into inline help

## Current Documentation Structure

```
docs/
├── PRD.md              # Current v1.0 product requirements
├── ROADMAP.md          # Progress tracker + future versions
├── PROPOSALS.md        # Optional extensions (Fabric, observability, etc.)
├── chat/               # Chat-specific docs (active prompts only)
│   ├── FABRIC_PATTERN_task-create.md
│   └── FABRIC_PROMPT_village-chat.md
├── examples/           # Working examples
│   ├── 01-quickstart/
│   ├── 02-configuration/
│   ├── 03-commands/
│   ├── 04-configuration/
│   └── 05-advanced/
└── SHELL_COMPLETION.md
```

## Why Consolidate?

The previous structure had 7 separate PRD/roadmap documents, making it difficult to:
- Understand the current implementation status
- Track progress toward goals
- Plan future work

The new structure provides:
- **Single source of truth** for current vision (PRD.md)
- **Clear progress tracking** with completion status (ROADMAP.md)
- **Separation of concerns** for optional ideas (PROPOSALS.md)

## Historical Context

These archived documents preserve the evolution of Village's design thinking. They are kept for reference but should not be considered active specifications.
