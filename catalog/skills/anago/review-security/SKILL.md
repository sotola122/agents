---
name: review-security
description: >-
  Anago review lane: auth, secrets, input handling, and supply-chain risk. Use for security-focused review.
---

# Review lane: security

Run as a **readonly** Anago review lane under the single `reviewer` agent.

## Focus

- Authentication, authorization, and session handling
- Secrets, credentials, and sensitive logging
- Input validation, injection, path traversal
- Supply-chain and dependency trust boundaries touched by the change

## Output

Findings with `dimension: security`. Mark exploitability and blast radius in impact. Never include real secret values in evidence.

## Rules

- Stay threat-focused; skip pure style nits.
