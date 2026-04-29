---
id: guardrails/forbidden_patterns
desc: Prohibit hardcoded secrets, placeholders, and low-quality content.
priority: 100
tags: [quality:content]
---

## Forbidden Content Guardrails

- **NO hardcoded secrets:** API keys, passwords, tokens, or connection strings must never appear in source code. Use environment variables or a secrets manager.
- **NO placeholder content:** Do not leave `TODO`, `FIXME`, `HACK`, `XXX`, or `TEMP` in committed code unless linked to a tracked issue.
- **NO debug artifacts:** Remove `console.log`, `print()`, `fmt.Println`, `debugger` statements, and commented-out code before committing.
- **NO overly verbose commentary:** Avoid "as previously mentioned," "it is important to note," or other filler. Be concise.
- **NO markdown tables wider than 10 columns** — use lists or structured formats instead.
- **NO absolute paths** in documentation or code comments. Use relative paths or symbolic references.
- **NO large binary blobs** in git. Use LFS or external storage for assets >1 MB.
