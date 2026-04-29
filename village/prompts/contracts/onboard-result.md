---
id: onboard-result
title: Onboard Result Contract
description: Structured output from onboarding interview
priority: 100
tags: [output:json]
---

## Output Contract

After the interview completes, output a JSON result:

```json
{
  "agents_md": "complete AGENTS.md content",
  "readme_md": "complete README.md content",
  "wiki_seeds": [
    {"filename": "project-overview.md", "content": "markdown content"},
    {"filename": "conventions.md", "content": "markdown content"}
  ],
  "self_critique": {
    "score": 85,
    "weakest_sections": ["section1", "section2", "section3"],
    "rewrites": {
      "section1": "improved content"
    }
  }
}
```

### Rules
- AGENTS.md must be complete and specific (no placeholder text)
- README.md must include real commands from the interview
- Wiki seeds should cover 2-3 key aspects of the project
- Self-critique: rate your output 1-100, identify 3 weakest sections, rewrite them
