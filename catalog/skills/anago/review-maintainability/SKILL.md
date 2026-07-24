---
name: review-maintainability
description: >-
  Anago review lane: clarity, operability, and change cost. Use when reviewing long-term maintainability.
---

# Review lane: maintainability

Run as a **readonly** Anago review lane under the single `reviewer` agent.

## Focus

- Clarity of names, structure, and control flow
- Operability (logs, metrics, debuggability)
- Cost of future change and duplication
- Dead code, misleading comments, and API footguns

## Output

Findings with `dimension: maintainability`. Tie each finding to change cost or operator pain.

## Rules

- Prefer high-signal issues; avoid pure taste debates.
