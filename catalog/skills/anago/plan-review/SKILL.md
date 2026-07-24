---
name: plan-review
description: >-
  Anago plan review: critique a Cursor standard plan without implementing it.
  Use for /plan-review or when validating plan quality before build work.
---

# Plan review

Review a Cursor **standard Plan Mode** plan for an active Anago project.
Do **not** replace Plan Mode, rewrite the plan into a custom planning system, or implement the plan.

## Preconditions

1. Confirm `.anago/project.json` exists. If absent, stop and explain that Anago is inactive for this project.
2. Identify the plan under review (open Plan Mode artifact, `.anago/plans/*`, or user-attached plan text).

## Focus

- Goal clarity vs scope / non-goals
- Assumptions called out vs hidden
- Acceptance criteria that are testable and complete
- Constraints, risks, and irreversible decisions
- Verification and rollback adequacy
- Relevant project knowledge / context gaps
- Over-specification of implementation before exploration (when the area is unknown)

## Procedure

1. Read the plan and any linked requirements, decisions, or knowledge notes.
2. Compare the plan to Anago Plan-extension expectations: non-goals, constraints, acceptance criteria, verification, rollback, and knowledge hooks.
3. Classify issues: Blocker, Major, Minor, Nit (or Anago finding severities when emitting structured findings).
4. State approval conditions: what must change before implementation starts.

## Output

- Concise verdict: approve / approve-with-conditions / revise
- Findings with evidence (quoted plan sections or missing sections)
- Concrete revision guidance (what to add or cut)
- Explicit reminder: do not implement during this review

## Rules

- Readonly relative to product code; do not start implementation.
- Do not invent requirements; if the plan is silent, record that as a gap.
- Prefer minimal, actionable fixes over rewriting the whole plan.
