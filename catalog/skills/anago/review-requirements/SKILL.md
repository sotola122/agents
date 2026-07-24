---
name: review-requirements
description: >-
  Anago review lane: intent, acceptance criteria, and scope. Use when reviewing whether changes match stated requirements or a plan.
---

# Review lane: requirements

Run as a **readonly** Anago review lane under the single `reviewer` agent. Do not invent findings outside this dimension.

## Focus

- Stated intent vs delivered change
- Acceptance criteria coverage and gaps
- Scope creep, missing requirements, ambiguous criteria
- User-visible behavior vs promised outcomes

## Output

Emit findings compatible with Anago `review-finding` (`dimension: requirements`). Each finding needs severity, confidence, evidence, impact, remediation, and verification. Prefer concrete paths, quotes, or acceptance-criterion IDs as evidence.

## Rules

- Stay inside this lane; do not run other review skills here.
- Do not implement fixes.
- If requirements are undocumented, record that as a finding or assumption — do not invent criteria.
