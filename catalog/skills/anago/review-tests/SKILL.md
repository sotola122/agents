---
name: review-tests
description: >-
  Anago review lane: test oracles, negative cases, and flakiness. Use when reviewing test quality for a change.
---

# Review lane: tests

Run as a **readonly** Anago review lane under the single `reviewer` agent.

## Focus

- Oracle quality (asserts the right behavior)
- Missing negative / edge cases
- Flakiness, order dependence, time/network coupling
- Coverage of new risk surfaces introduced by the change

## Output

Findings with `dimension: tests`. Point at test files and the production behavior they fail to pin.

## Rules

- Prefer actionable missing cases over coverage-percentage lectures.
