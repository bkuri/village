---
id: scribe-answer
title: Scribe Answer Contract
description: Structured answer with citations for knowledge base queries
priority: 100
tags: [output:structured]
---

## Output Contract

Respond with a structured answer:

### Format

```
## Answer
<synthesized answer text>

### Sources
- [page-id] — relevant quote or summary
- [page-id] — relevant quote or summary

### Confidence: high | unverified | not-found
```

### Rules
- Every factual claim must have a [page-id] citation
- Quotes must be exact or clearly paraphrased
- Confidence levels:
  - **high**: Directly supported by one or more wiki pages
  - **unverified**: Related information found but not a complete answer
  - **not-found**: No relevant information in wiki
