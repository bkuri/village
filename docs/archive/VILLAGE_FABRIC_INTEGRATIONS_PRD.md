# Village PRD — Fabric Integrations (ROI‑Sorted)

## Status
Draft — optional extensions for v1.x → v2

This document defines where Fabric-style LLM integrations provide clear value
without compromising Village’s core guarantees.

Fabric is treated as an optional text-artifact backend, never as a decision engine.

---

## Core Principle

Fabric may generate text artifacts only.
Village alone performs execution, scheduling, and arbitration.

---

## ROI‑Sorted Integrations

### Tier 1 — Extremely High ROI

1. village chat  
2. agent contract generation

### Tier 2 — High ROI

3. task drafting (human-approved)  
4. digest / project summary

### Tier 3 — Medium ROI

5. PR description generator  
6. release notes generation

---

## Safety Rules

- no execution decisions
- no implicit side effects
- file-backed outputs only
- explicit invocation required

---

## Summary

Fabric enhances Village by generating durable knowledge artifacts while
Village remains deterministic and debuggable.