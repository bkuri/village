---
id: guardrails/tdd
desc: Enforce test-driven development discipline.
priority: 100
tags: [discipline:strict]
---

## TDD Guardrails

- **NEVER write implementation code before tests.**
- **ALWAYS write a failing test first** — this is non-negotiable.
- **Run the test. Confirm it fails.** Only then write the minimum code to make it pass.
- **After the test passes, refactor** while keeping all tests green.
- **Do not skip tests** because the change seems "trivial" or "obvious."
- **Every bug fix must include a regression test** that reproduces the bug before the fix.
- **Integration/e2e tests** go in `tests/`. Unit tests live next to the code they test (`*_test.go`, `test_*.py`, etc.).
- **Coverage minimums are defined in project config** — do not submit code that drops coverage.

This policy is verified by post-hoc scan at commit time. Violations block the commit.
