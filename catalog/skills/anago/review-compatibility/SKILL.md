---
name: review-compatibility
description: >-
  Anago review lane: API, schema, and migration compatibility. Use when reviewing breaking-change risk.
---

# Review lane: compatibility

Run as a **readonly** Anago review lane under the single `reviewer` agent.

## Focus

- Public API and CLI contract changes
- Schema / config compatibility
- Migrations, versioning, and rollback paths
- Client/server or cross-package skew

## Output

Findings with `dimension: compatibility`.

## Rules

- Call out silent breaks and missing migration notes explicitly.
