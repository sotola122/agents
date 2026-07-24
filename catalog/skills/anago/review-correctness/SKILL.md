---
name: review-correctness
description: >-
  Anago review lane: logic, boundaries, and invariants. Use when checking behavioral correctness of a change.
---

# Review lane: correctness

Run as a **readonly** Anago review lane under the single `reviewer` agent.

## Focus

- Control flow, edge cases, and error paths
- Boundary conditions and validation
- Invariants, preconditions, and postconditions
- Off-by-one, null/empty, race, and state-machine mistakes

## Output

Findings with `dimension: correctness`. Cite files, symbols, and failing scenarios. Separate confirmed bugs from speculative risks via confidence.

## Rules

- Evidence-backed only; no speculative rewrites.
- Do not broaden into security or performance unless the defect is primarily a correctness bug.
