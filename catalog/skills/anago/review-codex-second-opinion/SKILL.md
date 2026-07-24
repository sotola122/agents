---
name: review-codex-second-opinion
description: >-
  Anago optional Codex harness review via delegate-codex. Use only when defaults/reviews.json delegateCodex.enabled is true.
---

# Review: Codex second opinion

Optional harness lane for the Anago `reviewer` agent.

## Config gate

Read project/global Anago review config (`defaults/reviews.json` overlay):

- Invoke this workflow **only if** `delegateCodex.enabled` is `true`.
- If disabled, skip silently and rely on Cursor-internal lane skills. Do not call Codex CLI.

## How

1. Follow the `delegate-codex` skill (`skills/delegate-codex` in the agents catalog / `~/.agents/skills/delegate-codex`).
2. Use the `review` permission profile (read-only).
3. Pass a sealed or bounded scope: merge-base diff, named paths, and Anago finding schema expectations.
4. Surface Codex stdout as an independent opinion; then fold into `review-synthesis` without inventing extra findings.

## Rules

- Never start the interactive Codex TUI for this lane.
- On auth/timeout/failure, report the failure visibly and fall back to Cursor-internal lanes.
