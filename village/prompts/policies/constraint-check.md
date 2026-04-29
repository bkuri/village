---
id: constraint-check
title: Project Constraint Validation
description: Check task proposals against project context
requires: [base]
tags: []
---

Before finalizing a task manifest, validate against project context to surface conflicts, blockers, and hidden risks.

## What to Check

### 1. Goal Alignment (goals.md)

**Question:** Does this task help achieve stated goals?

**Check:**
- Scan `goals.md` for strategic goals.
- Compare task scope to goals.

**Output:**
- If aligned: Note which goals this task advances in `llm_notes`.
- If misaligned: Ask "This task builds X, but our goals focus on Y. Are we on track?"

**Example:**
- Task: "Add Redis caching"
- Goals: "improve-performance", "scalability"
- Result: ✅ Aligned (both goals mention performance)
- Note: "Advances 'improve-performance' and 'scalability' goals"

---

### 2. Constraint Violations (constraints.md)

**Question:** Does this task violate any documented constraints?

**Check:**
- Scan `constraints.md` for technical, business, and process constraints.
- Compare task requirements to constraints.

**Output:**
- If no violations: Confirm in `llm_notes`.
- If violation found: Ask clarifying question.

**Example:**
- Task: "Add Redis caching"
- Constraint: "No external services allowed"
- Result: ⚠️ Violation detected
- Ask: "This task requires Redis, but our constraint says 'no external services'. Should we: a) Revise constraint, b) Choose different approach, c) Defer task?"

---

### 3. Decision Conflicts (decisions.md)

**Question:** Does this task contradict existing decisions?

**Check:**
- Scan `decisions.md` for architectural or strategic decisions.
- Compare task approach to decisions.

**Output:**
- If no conflicts: Confirm in `llm_notes`.
- If conflict found: Ask clarifying question.

**Example:**
- Task: "Switch from Postgres to MySQL"
- Decision: "We decided on Postgres for ACID compliance"
- Result: ⚠️ Conflict detected
- Ask: "This switches to MySQL, but we decided on Postgres. Why the change? Is there a new requirement?"

---

### 4. Blockers and Dependencies (open-questions.md + context)

**Question:** Are there unresolved blockers or dependencies?

**Check:**
- Scan `open-questions.md` for related questions.
- Review task's own blockers field.
- Check context for implicit dependencies (e.g., "This depends on feature X" but X isn't done).

**Output:**
- If blockers exist: Surface them clearly in manifest `blockers` field.
- If no blockers: Confirm in `llm_notes`.

**Example:**
- Task: "Add Redis caching"
- Context: "Redis deployment hasn't been approved by infra"
- Result: ⚠️ Blocker detected
- Note: "Depends on infra approval (documented in blockers)"

---

## Validation Pattern

For each check above:

1. **Read context.** Scan the relevant context file.
2. **Compare.** Match task against context.
3. **Surface.** If issue found, output:
   - "I see a potential issue: [issue description]"
   - "Should we: [option A, option B, option C]?"
4. **Await user response.** Don't proceed to Phase 5 until resolved or acknowledged.
5. **Update.** If user clarifies, update manifest, re-check.

## What to Avoid

- **Don't block.** The user decides; you only surface issues.
- **Don't assume.** If context is ambiguous, ask. E.g., "Constraint says 'no external services'—is Redis considered external, or foundational infrastructure?"
- **Don't over-validate.** Check each area once; don't cycle endlessly.

## LLM Notes Format

Use `llm_notes` to document validation results:
```json
{
  "llm_notes": [
    "Confirmed alignment with goal: improve-performance",
    "No constraint violations detected",
    "No decision conflicts detected",
    "Blocker noted: infra approval required"
  ]
}
```

INPUT:
