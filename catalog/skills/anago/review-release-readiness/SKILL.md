---
name: review-release-readiness
description: >-
  Anago review lane: rollback, versioning, and release evidence. Use before ship or release gates.
---

# Review lane: release-readiness

Run as a **readonly** Anago review lane under the single `reviewer` agent.

## Focus

- Version bumps, changelogs, and release notes
- Rollback / forward-fix strategy
- Required verification evidence (tests, smoke, docs)
- Feature flags and kill switches when relevant

## Output

Findings with `dimension: release-readiness`.

## Rules

- Do not claim ship-ready without citing evidence that exists in-repo or was run.
