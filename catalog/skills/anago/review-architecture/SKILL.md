---
name: review-architecture
description: >-
  Anago review lane: dependencies, responsibilities, and contracts. Use when reviewing module boundaries and design fit.
---

# Review lane: architecture

Run as a **readonly** Anago review lane under the single `reviewer` agent.

## Focus

- Module/package responsibilities and layering
- Dependency direction and coupling
- Public contracts, API surface, and ownership
- Deep-module vs leaky abstraction risks introduced by the change

## Output

Findings with `dimension: architecture`. Prefer structural evidence (imports, call paths, package layout) over style opinions.

## Rules

- Judge fit against existing architecture; do not propose greenfield redesigns unless the change already forces one.
