---
name: review-performance-reliability
description: >-
  Anago review lane: complexity, resources, recovery, and reliability. Use when reviewing perf and resilience.
---

# Review lane: performance-reliability

Run as a **readonly** Anago review lane under the single `reviewer` agent.

## Focus

- Algorithmic complexity and hot paths
- Resource use (CPU, memory, IO, connections)
- Timeouts, retries, backoff, and idempotency
- Failure recovery and degradation behavior

## Output

Findings with `dimension: performance-reliability`. Prefer measured or clearly reasoned evidence over vague 'might be slow'.

## Rules

- Skip micro-optimizations unrelated to the change.
