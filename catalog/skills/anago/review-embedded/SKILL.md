---
name: review-embedded
description: >-
  Anago review lane: ISR, RTOS, flash, timing, power, and protocols. Use for embedded/firmware changes.
---

# Review lane: embedded

Run as a **readonly** Anago review lane under the single `reviewer` agent. Skip if the change is not embedded/firmware-related and say so briefly.

## Focus

- ISR safety, concurrency with main loop / RTOS tasks
- Flash wear, NVS, and persistence integrity
- Timing deadlines, jitter, and watchdog interaction
- Power states and peripheral/protocol correctness

## Output

Findings with `dimension: embedded`.

## Rules

- If out of domain, return no findings with a one-line not-applicable note.
