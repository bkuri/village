---
id: task-manifest
title: Task Manifest Schema
description: JSON schema for task-creation mode output
requires: []
tags: []
---

# Task Manifest Schema

When in **task-creation mode**, your output must match this exact JSON structure:

```json
{
  "id": "draft-abc123",
  "title": "Add Redis caching layer",
  "description": "Cache API responses to reduce database load during peak hours",
  "scope": "feature|fix|investigation|refactoring",
  "relates_to_goals": ["goal-1", "goal-2"],
  "success_criteria": ["criterion-1", "criterion-2"],
  "blockers": ["blocker-1"],
  "estimate": "hours|days|weeks|unknown",
  "tags": ["tag-1", "tag-2"],
  "notes": ["note-1", "note-2"],
  "llm_notes": ["internal-llm-note-1"]
}
```

## Required Fields

### `id` (string, required)

Draft task ID in format `draft-<8-char-uuid>`.

**Example:** `"draft-abc123"`

---

### `title` (string, required, 5-15 words)

Task title: concise, specific, and actionable.

**Rules:**
- **5-15 words max.** Don't be verbose.
- **Specific.** "Add Redis caching" ✅, not "Improve performance" ❌.
- **Actionable.** "Fix auth timeout" ✅, not "Investigate auth" ❌.

---

### `description` (string, required, 1-3 sentences)

Brief description of what the task does and why it matters.

**Rules:**
- **1-3 sentences.** Concise but informative.
- **Includes why.** "Cache API to reduce load" (not just "Cache API").
- **No bullet points.** Paragraph form preferred.

---

### `scope` (string, required, enum)

Type of work. Must be one of:
- `feature`: New functionality
- `fix`: Bug fix
- `investigation`: Research or debugging
- `refactoring`: Code improvement without behavior change

**Example:** `"feature"`

---

### `relates_to_goals` (array of strings, optional, default: [])

Goal IDs from `goals.md` that this task advances.

**Rules:**
- **Reference existing goals.** Goal names or IDs from goals.md context.
- **Empty array if none.** `[]` is valid.

**Example:** `["improve-performance", "scalability"]`

---

### `success_criteria` (array of strings, required)

Measurable outcomes that indicate task completion.

**Rules:**
- **Specific and measurable.** "API response < 100ms" ✅, not "faster" ❌.
- **1-5 criteria.** Don't over-spec; focus on what matters.
- **Addressable by implementation.** "Pass all unit tests" ✅, not "works well" ❌.

**Examples:**
```json
{
  "success_criteria": [
    "API response times < 100ms for cached endpoints",
    "Cache hit rate > 80%",
    "Memory usage < 500MB"
  ]
}
```

---

### `blockers` (array of strings, optional, default: [])

Items preventing task from starting or completing.

**Rules:**
- **Specific.** "Redis deployment TBD" ✅, not "infra" ❌.
- **External dependencies noted.** E.g., "Needs AWS approval" or "Requires feature X to land first".

**Example:**
```json
{
  "blockers": [
    "Need to decide Redis deployment strategy (single instance vs cluster)",
    "Waiting for infra team approval for new service"
  ]
}
```

---

### `estimate` (string, required, enum)

Rough effort estimate. Must be one of:
- `hours`: < 1 day of work
- `days`: 1-5 days
- `weeks`: > 1 week
- `unknown`: Effort unclear (requires investigation first)

**Example:** `"days"`

---

### `tags` (array of strings, optional, default: [])

Keywords for categorization and discovery.

**Rules:**
- **Lowercase, kebab-case.** `["performance", "infrastructure"]`, not `["Performance", "Infrastructure"]`.
- **Relevant to task.** Don't add noise.

**Example:** `["performance", "infrastructure", "backend"]`

---

### `notes` (array of strings, optional, default: [])

User-provided information or clarifications that surfaced during Q&A.

**Example:**
```json
{
  "notes": [
    "User mentioned this needs to work with existing session management",
    "Business stakeholder wants this for Q4 release"
  ]
}
```

---

### `llm_notes` (array of strings, optional, default: [])

Internal LLM metadata for context (not shown to user).

**Use cases:**
- Document validation results (e.g., "Confirmed no constraint violations").
- Note related tasks (e.g., "Suggested follow-up: add cache monitoring").
- Explain rationale for decisions.

**Example:**
```json
{
  "llm_notes": [
    "Confirmed alignment with goal: improve-performance",
    "No constraint violations detected",
    "Suggested related task: add monitoring for cache metrics"
  ]
}
```

---

## Validation Rules

1. **Must be valid JSON.** Wrap in markdown code fences: ```json ... ```
2. **All required fields present.** `id`, `title`, `description`, `scope`, `success_criteria`, `estimate`.
3. **Scope is valid enum.** Must be `feature|fix|investigation|refactoring`.
4. **Estimate is valid enum.** Must be `hours|days|weeks|unknown`.
5. **Title length.** 5-15 words.
6. **Success criteria measurable.** Each criterion must be specific and testable.
7. **ID format.** Must start with `draft-` and be 8 hex chars.

## Example Complete Output

```json
{
  "id": "draft-abc123",
  "title": "Add Redis caching layer",
  "description": "Cache API responses to reduce database load during peak hours",
  "scope": "feature",
  "relates_to_goals": ["improve-performance", "scalability"],
  "success_criteria": [
    "API response times < 100ms for cached endpoints",
    "Cache hit rate > 80%",
    "No increase in memory usage > 500MB"
  ],
  "blockers": [
    "Need to decide Redis deployment strategy (single instance vs cluster)"
  ],
  "estimate": "days",
  "tags": ["performance", "infrastructure"],
  "notes": [
    "User mentioned this needs to work with existing session management",
    "Consider cache invalidation strategy"
  ],
  "llm_notes": [
    "Confirmed this doesn't violate constraint about immutable data structures",
    "Suggested related task: add monitoring for cache metrics"
  ]
}
```

INPUT:
