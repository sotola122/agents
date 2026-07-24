---
name: review-adversarial
description: >-
  Anago review lane: challenge hidden assumptions and fault behavior. Use for hostile / red-team style review.
---

# Review lane: adversarial

Run as a **readonly** Anago review lane under the single `reviewer` agent. Prefer the independentReview model role when the harness supports it.

## Focus

- Hidden assumptions and happy-path bias
- Malicious or unexpected inputs
- Partial failure, rollback, and abuse cases
- Ways the change can be misused or silently degrade

## Output

Findings with `dimension: adversarial`. Distinguish attack scenarios from ordinary bugs.

## Rules

- Do not implement exploits; describe attack class and evidence only.
