---
id: context-update
title: Context Update Schema
description: JSON schema for knowledge-sharing mode output
requires: []
tags: []
---

# Context Update Schema

When in **knowledge-sharing mode**, your output must match this exact JSON structure:

```json
{
  "writes": {
    "project.md": "# Project\\n\\nSummary (2-5 lines)...",
    "goals.md": "# Goals\\n\\n## Goals\\n- Goal 1\\n- Goal 2\\n\\n...",
    "constraints.md": "# Constraints\\n\\n## Technical\\n- ...\\n\\n## Business\\n- ...",
    "assumptions.md": "# Assumptions\\n\\n## Assumptions\\n- ...",
    "decisions.md": "# Decisions\\n\\n## Decisions\\n- ...\\n\\n## Rationale\\n...\"",
    "open-questions.md": "# Open Questions\\n\\n## Questions\\n- Q1 (priority: high)\\n- Q2 (priority: medium)..."
  },
  "notes": ["Optional metadata from LLM"],
  "open_questions": ["Optional extracted questions"]
}
```

## Required Fields

### `writes` (object, required)

Map of filename → markdown content. Keys are:
- `project.md`: Project summary and scope
- `goals.md`: Strategic goals (bullet list)
- `constraints.md`: Technical, business, process constraints (categorized)
- `assumptions.md`: Shared assumptions (categorized)
- `decisions.md`: Architectural/strategic decisions with rationale
- `open-questions.md`: Unresolved questions (prioritized)

**Rules:**
- **Incremental updates.** Don't rewrite entire files if just adding to them. E.g., for `goals.md`, only append new goals if they're different.
- **Markdown format.** Each file must start with `# Title\\n\\n`.
- **Valid filenames only.** Only the 6 keys listed above are valid.

### `notes` (array of strings, optional)

Internal metadata for context updates. Examples:
- "Added goal: improve performance"
- "Documented constraint: data locality required"
- "Updated project scope based on user feedback"

### `open_questions` (array of strings, optional)

Questions that emerged during conversation. These get merged into `open-questions.md` file.

**Example:**
```json
{
  "open_questions": [
    "Should we use Redis or Memcached? (priority: high)",
    "Is deployment to AWS or on-prem? (priority: medium)"
  ]
}
```

## Validation Rules

1. **Must be valid JSON.** Wrap in markdown code fences: ```json ... ```
2. **Required field present.** `writes` must exist and be a non-empty object.
3. **Valid filenames.** Keys in `writes` must be one of the 6 canonical files.
4. **Markdown content.** Values in `writes` must be strings containing markdown.
5. **Incremental updates.** When updating existing files, prefer appending/restructuring over full replacement (document in `notes`).

## Error Handling

If context files don't exist yet:
- Create them with initial content.
- Don't fail—first-time setup is expected.

INPUT:
