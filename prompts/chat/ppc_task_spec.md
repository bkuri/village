# PPC Task Specification - LLM Prompt Policy

## Purpose

This policy defines how LLMs should interpret natural language task descriptions and extract structured task specifications, with special focus on **dependency recognition** for the Beads task management system.

## Dependency Pattern Recognition

### Blocking Relationships

When a task **blocks** another task (i.e., this task must complete before others can start):

| Pattern | Interpretation |
|---------|---------------|
| "blocks X" | `blocks: ["X"]` |
| "blocks [task]" | `blocks: ["[task-id]"]` |
| "must complete before [task]" | `blocks: ["[task-id]"]` |
| "prerequisite for [task]" | `blocks: ["[task-id]"]` |
| "required for [task]" | `blocks: ["[task-id]"]` |

### Blocked By Relationships

When a task is **blocked by** another task (i.e., cannot start until dependencies complete):

| Pattern | Interpretation |
|---------|---------------|
| "blocked by Y" | `blocked_by: ["Y"]` |
| "blocked by [task]" | `blocked_by: ["[task-id]"]` |
| "depends on Z" | `blocked_by: ["Z"]` |
| "depends on [task]" | `blocked_by: ["[task-id]"]` |
| "cannot start until A" | `blocked_by: ["A"]` |
| "waiting on A" | `blocked_by: ["A"]` |
| "needs [task] first" | `blocked_by: ["[task-id]"]` |
| "requires [task] to complete" | `blocked_by: ["[task-id]"]` |

### Task Identification Strategies

1. **Exact Beads IDs (highest priority)**
   - Format: `bd-abc123`, `bd-def456`
   - Always use the exact ID when present
   - Example: "blocks bd-a3f8" → `blocks: ["bd-a3f8"]`

2. **Task Names (convert to kebab-case)**
   - Convert multi-word names to kebab-case
   - Example: "dashboard widget" → `dashboard-widget`
   - Example: "user authentication" → `user-authentication`
   - Example: "blocks the API redesign" → `blocks: ["api-redesign"]`

3. **Pronouns and References**
   - "blocks it", "blocked by that" → **ALWAYS set `needs_clarification: true`**
   - Provide clarification question
   - Suggest possible task IDs based on context

## JSON Output Format

```json
{
  "title": "Concise task title",
  "description": "Detailed description of what needs to be done",
  "scope": "fix|feature|config|docs|test|refactor",
  "blocks": ["task-id-1", "task-id-2"],
  "blocked_by": ["task-id-3", "task-id-4"],
  "success_criteria": [
    "Criterion 1: Specific, measurable outcome",
    "Criterion 2: Another measurable outcome",
    "Criterion 3: Final verification step"
  ],
  "estimate": "2-3 hours|days|weeks",
  "confidence": "high|medium|low",
  "needs_clarification": false,
  "clarification_question": null,
  "suggested_tasks": []
}
```

### Field Specifications

- **title**: 3-10 words, clear and action-oriented
- **description**: 2-5 sentences, what + why + how
- **scope**: One of: `fix`, `feature`, `config`, `docs`, `test`, `refactor`
- **blocks**: Array of task IDs this task blocks (optional)
- **blocked_by**: Array of task IDs that block this task (optional)
- **success_criteria**: 3-5 specific, measurable outcomes
- **estimate**: Time range with unit (hours, days, weeks)
- **confidence**: `high`, `medium`, or `low` based on clarity
- **needs_clarification**: `true` if ambiguity detected
- **clarification_question**: Question to resolve ambiguity
- **suggested_tasks**: List of likely task IDs for ambiguous references

## Detailed Examples

### Example 1: Task with Exact Beads ID

**User Input:**
```
Update the authentication middleware to use JWT tokens. This blocks bd-a3f8 
because the API endpoints need the new auth format before they can be tested.
```

**Extracted JSON:**
```json
{
  "title": "Update authentication middleware to use JWT",
  "description": "Replace existing authentication middleware with JWT token-based authentication to improve security and stateless session management.",
  "scope": "feature",
  "blocks": ["bd-a3f8"],
  "blocked_by": [],
  "success_criteria": [
    "JWT token generation and validation implemented",
    "Middleware successfully verifies tokens on protected routes",
    "Existing tests pass with new auth flow",
    "No regression in current authenticated endpoints"
  ],
  "estimate": "1-2 days",
  "confidence": "high",
  "needs_clarification": false,
  "clarification_question": null,
  "suggested_tasks": []
}
```

**Dependency Extraction Explanation:**
- Detected pattern: "blocks bd-a3f8"
- Extracted exact Beads ID: `bd-a3f8`
- Reasoning: User provided an explicit Beads ID in standard format
- Added to `blocks` array because this task must complete before bd-a3f8 can proceed

---

### Example 2: Task with Task Name Pattern

**User Input:**
```
Implement the dashboard widget component. This blocks the dashboard integration 
task, and it depends on the API response format being finalized.
```

**Extracted JSON:**
```json
{
  "title": "Implement dashboard widget component",
  "description": "Create a reusable dashboard widget component with configurable options for displaying data visualization and metrics.",
  "scope": "feature",
  "blocks": ["dashboard-integration"],
  "blocked_by": ["api-response-format"],
  "success_criteria": [
    "Widget component renders correctly with test data",
    "Component accepts configuration props for customization",
    "Widget handles loading and error states gracefully",
    "Component is tested with multiple data types",
    "Integration with dashboard layout verified"
  ],
  "estimate": "3-5 days",
  "confidence": "medium",
  "needs_clarification": false,
  "clarification_question": null,
  "suggested_tasks": []
}
```

**Dependency Extraction Explanation:**
- Detected pattern: "blocks the dashboard integration task"
- Converted task name: "dashboard integration" → `dashboard-integration`
- Detected pattern: "depends on the API response format"
- Converted task name: "API response format" → `api-response-format`
- Reasoning: User described tasks in natural language with clear names, converted to kebab-case for consistency

---

### Example 3: Task Blocked by Something

**User Input:**
```
Add unit tests for the payment processing module. This cannot start until the 
refactoring is complete because the internal API is changing.
```

**Extracted JSON:**
```json
{
  "title": "Add unit tests for payment processing",
  "description": "Create comprehensive unit tests for the payment processing module to ensure code quality and prevent regressions.",
  "scope": "test",
  "blocks": [],
  "blocked_by": ["refactoring"],
  "success_criteria": [
    "Unit tests cover all payment processing functions",
    "Tests achieve at least 80% code coverage",
    "Mock payment gateway dependencies properly",
    "Tests verify error handling and edge cases",
    "All tests pass consistently in CI pipeline"
  ],
  "estimate": "2-3 days",
  "confidence": "medium",
  "needs_clarification": false,
  "clarification_question": null,
  "suggested_tasks": []
}
```

**Dependency Extraction Explanation:**
- Detected pattern: "cannot start until the refactoring is complete"
- Converted task name: "refactoring" → `refactoring`
- Reasoning: User explicitly stated a precondition for this task
- Added to `blocked_by` array because this task depends on the refactoring completing first

---

### Example 4: Task with Both Blocks and Blocked By

**User Input:**
```
Implement the user profile update endpoint. This is blocked by the database 
schema changes, but it blocks both the frontend profile page and the admin 
user management feature.
```

**Extracted JSON:**
{
  "title": "Implement user profile update endpoint",
  "description": "Create a REST API endpoint for updating user profiles, including validation, authentication, and proper error handling.",
  "scope": "feature",
  "blocks": ["frontend-profile-page", "admin-user-management"],
  "blocked_by": ["database-schema-changes"],
  "success_criteria": [
    "Endpoint accepts PUT/PATCH requests to /users/:id",
    "Request payload validation enforced",
    "Only authenticated users can update their own profile",
    "Admin users can update any profile",
    "Proper error responses for invalid requests",
    "Database updates are atomic and consistent"
  ],
  "estimate": "2-3 days",
  "confidence": "high",
  "needs_clarification": false,
  "clarification_question": null,
  "suggested_tasks": []
}
```

**Dependency Extraction Explanation:**
- Detected pattern: "blocked by the database schema changes"
- Converted task name: "database schema changes" → `database-schema-changes`
- Added to `blocked_by` array
- Detected pattern: "blocks both the frontend profile page and the admin user management feature"
- Converted task names:
  - "frontend profile page" → `frontend-profile-page`
  - "admin user management feature" → `admin-user-management`
- Added both to `blocks` array
- Reasoning: This task has both upstream dependencies (things it needs) and downstream dependencies (things that need it)

---

### Example 5: Ambiguous Reference (Needs Clarification)

**User Input:**
```
Fix the bug in the payment processing code. This blocks it and is also blocked 
by the refactoring that was mentioned in the meeting.
```

**Extracted JSON:**
```json
{
  "title": "Fix payment processing bug",
  "description": "Identify and resolve the bug in the payment processing code that is causing issues with transaction handling.",
  "scope": "fix",
  "blocks": [],
  "blocked_by": ["refactoring"],
  "success_criteria": [
    "Bug is identified and root cause documented",
    "Fix is implemented and tested",
    "No regressions introduced",
    "Payment processing works correctly in all scenarios"
  ],
  "estimate": "1-2 days",
  "confidence": "low",
  "needs_clarification": true,
  "clarification_question": "You mentioned 'blocks it' but didn't specify which task. Which task does this payment processing fix block?",
  "suggested_tasks": [
    "payment-integration",
    "transaction-history",
    "checkout-flow",
    "payment-testing"
  ]
}
```

**Dependency Extraction Explanation:**
- Detected pattern: "blocked by the refactoring"
- Converted task name: "refactoring" → `refactoring`
- Added to `blocked_by` array (clear reference)
- Detected ambiguous pattern: "blocks it"
- Did NOT add to `blocks` array (pronoun reference is ambiguous)
- Set `needs_clarification: true` because "it" is undefined
- Provided `clarification_question` asking for specific task
- Suggested likely tasks based on context (payment-related tasks)
- Set `confidence: "low"` due to ambiguity

## Ambiguity Detection Rules

### Always Require Clarification When:

1. **Pronoun References**
   - "blocks it", "blocks that", "blocks this"
   - "blocked by it", "blocked by that", "blocked by this"
   - "depends on it", "waiting on that"

2. **Incomplete References**
   - "blocks the other task"
   - "blocked by the feature"
   - "depends on the one we discussed"

3. **Multiple Possible Interpretations**
   - Task names that match multiple existing tasks
   - Vague descriptions that could apply to several tasks

### How to Handle Ambiguity

1. Set `needs_clarification: true`
2. Set `confidence: "low"` (unless other parts are clear)
3. Provide `clarification_question` with:
   - What specifically is unclear
   - What information is needed
4. Provide `suggested_tasks` with:
   - 3-5 likely task IDs based on context
   - Reasonably specific but not exhaustive
5. Still extract any clear dependencies
   - Don't let ambiguity block all extraction
   - Extract what you can, flag what you can't

## Transparency Requirements

### What to ALWAYS Explain

1. **What dependencies were extracted**
   - List each extracted dependency
   - Show the original text pattern
   - Show the resulting task ID

2. **Why you interpreted it that way**
   - Explain pattern matching logic
   - Explain any conversions (e.g., kebab-case)
   - Explain confidence level

3. **When you're unsure**
   - Explicitly state uncertainty
   - Explain what makes it ambiguous
   - Ask for clarification
   - Provide reasoning for suggested tasks

### Transparency Format

After the JSON output, provide a brief explanation:

```
**Dependencies Extracted:**
- Blocks: [task-id] (detected from "blocks [pattern]")
- Blocked by: [task-id] (detected from "blocked by [pattern]")

**Interpretation:**
- Extracted [task-id] from "[original text]" because [reasoning]
- Confidence: [high/medium/low] because [reasoning]

**Clarification Needed:**
- [explanation of what's ambiguous]
- [suggested tasks with brief context]
```

## Edge Cases and Special Patterns

### Compound Dependencies

- "blocks A and B" → `blocks: ["A", "B"]`
- "blocked by X, Y, and Z" → `blocked_by: ["X", "Y", "Z"]`
- "depends on the auth system and the API" → `blocked_by: ["auth-system", "api"]`

### Conditional Dependencies

- "blocks A if we go with that approach" → Extract but note in description, maybe set lower confidence
- "might be blocked by B" → Extract but set `confidence: "low"` and note condition

### Indirect Dependencies

- "blocks the integration, which is needed for the rollout" → Extract direct dependency (`integration`), add context to description
- "waiting on the feature that's being built by the other team" → Try to identify feature name, else flag for clarification

### Self-References

- "blocks this task" → Invalid, ignore or flag as error
- "depends on itself" → Invalid, ignore or flag as error

## Quality Checklist

Before finalizing extraction, verify:

- [ ] All dependencies are extracted and properly categorized
- [ ] Task IDs follow kebab-case convention (unless exact Beads ID)
- [ ] Beads IDs are preserved exactly when provided
- [ ] Ambiguous references are flagged with `needs_clarification`
- [ ] Confidence level reflects actual certainty
- [ ] Transparency explanation is clear and complete
- [ ] No invalid or nonsensical dependencies
- [ ] JSON is valid and properly formatted

## Common Mistakes to Avoid

1. **Don't ignore dependencies** - Even if unsure, try to extract what you can
2. **Don't assume Beads IDs** - Only use exact IDs when explicitly provided
3. **Don't be overconfident** - Use "medium" or "low" confidence when appropriate
4. **Don't skip clarification** - Better to ask than to guess incorrectly
5. **Don't ignore context** - Use surrounding text to disambiguate references
6. **Don't mix up blocks/blocked_by** - Double-check directionality
7. **Don't forget to explain** - Transparency is required

## Examples of Common Patterns

### Natural to Structured

| Natural Language | Structured Output |
|----------------|------------------|
| "blocks bd-a3f8" | `blocks: ["bd-a3f8"]` |
| "blocked by the auth system" | `blocked_by: ["auth-system"]` |
| "depends on the API" | `blocked_by: ["api"]` |
| "cannot start until database is ready" | `blocked_by: ["database"]` |
| "prerequisite for the frontend" | `blocks: ["frontend"]` |
| "must complete before testing" | `blocks: ["testing"]` |
| "waiting on the design" | `blocked_by: ["design"]` |
| "needs the migration first" | `blocked_by: ["migration"]` |

## Conclusion

The goal is to extract dependencies accurately and transparently. When in doubt:

1. Extract what you can with appropriate confidence
2. Flag ambiguity explicitly
3. Ask for clarification
4. Provide context and reasoning
5. Never guess at task IDs - use exact IDs or kebab-case conversions

This ensures the Beads task management system receives accurate, actionable dependency information that can be used for task scheduling and execution planning.
