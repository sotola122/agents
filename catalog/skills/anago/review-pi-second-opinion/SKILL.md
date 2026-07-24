---
name: review-pi-second-opinion
description: >-
  Anago optional Pi harness review via delegate-pi. Use only when defaults/reviews.json delegatePi.enabled (or piCodex.enabled) is true.
---

# Review: Pi second opinion

Optional harness lane for the Anago `reviewer` agent.

## Config gate

Read project/global Anago review config (`defaults/reviews.json` overlay):

- Invoke **only if** `delegatePi.enabled` is `true` (treat `piCodex.enabled: true` as enabling Pi settings + this lane when `delegatePi` is absent in older configs).
- If disabled, skip. Do not run `pi`.

## How

1. Follow the `delegate-pi` skill (`skills/delegate-pi` / `~/.agents/skills/delegate-pi`).
2. Use the `review` profile (read-only tools).
3. Prefer Anago `piCodex.modelSpec` / provider settings when present; otherwise use delegate-pi `provider.yaml`.
4. Pass bounded scope (merge-base diff or sealed bundle). Surface Pi stdout; fold via `review-synthesis`.

## Rules

- Prefer `pi --print`; no interactive Pi session.
- On smoke/auth/timeout failure, stop the harness lane and report — do not silently substitute a local review as if it were Pi.
