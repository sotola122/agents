---
name: delegate-pi
description: >-
  Delegate a bounded coding task to the Pi coding agent via CLI (`pi --print`).
  Use when the user wants a second-opinion review, verification (build/test/lint),
  or implementation handed off to Pi, mentions running/delegating work to pi,
  or asks to smoke-test / confirm Pi connectivity.
---

# Delegate Pi

Hand one bounded task to Pi as a child agent. Prefer `--print` (process and exit).
Do not start interactive `pi` for delegation.

Prompt bodies live under [`prompts/`](prompts/). Review output shape is in [`prompts/review.md`](prompts/review.md).

## Steps

### 0. Smoke (only when asked)

When the user asks to smoke-test or confirm Pi auth / model / connectivity — and only then — run this step before (or instead of) a real task. Otherwise skip to step 1.

1. Read [provider.yaml](provider.yaml) → use `smoke.model` and `smoke.thinking` (not the default task model).
2. Run with `--no-tools` and the body of [`prompts/smoke.md`](prompts/smoke.md).

```bash
pi \
  --print \
  --provider <provider.yaml provider> \
  --model <provider.yaml smoke.model> \
  --thinking <provider.yaml smoke.thinking> \
  --no-session \
  --no-extensions \
  --no-skills \
  --no-prompt-templates \
  --no-context-files \
  --no-approve \
  --no-tools \
  "Reply with exactly: OK"
```

Completion: skipped (user did not ask), or stdout is exactly `OK` (trim whitespace) and exit code is 0. On any other smoke outcome (non-zero, empty, wrong text, auth/model error), **stop** and report the failure — do not run the real task.

### 1. Choose a permission profile

Read [profiles.yaml](profiles.yaml). Pick **exactly one** profile that matches the task:

| Task | Profile |
| --- | --- |
| Review, design check, static bug hunt | `review` |
| Build, test, lint, reproduce (no source edits intended) | `verify` |
| Implement, fix, refactor (user explicitly asked) | `implement` |
| Judge only text/diff already provided (no repo tools) | `no-tools` |

Map the profile to CLI flags:

- `tools: [...]` → `--tools` joined with commas
- `no_tools: true` → `--no-tools`
- Apply every `defaults:` flag as the matching `--flag`

Completion: the profile name and its tool flags are fixed. Do not invent tool lists.

### 2. Load provider settings

Read [provider.yaml](provider.yaml). Take `provider`, `model`, and `thinking` (use `thinking_by_task` when the task shape matches a key). Override only if the user names different values. Do **not** use the `smoke` block for the real task.

Completion: `--provider`, `--model`, and `--thinking` are set.

### 3. Assemble the prompt

Build one prompt file by concatenating, in order:

1. **Base** — `prompts/<profile>.md` when it exists (`review`, `verify`, `implement`). For `no-tools`, skip base or use a one-line instruction only.
2. **Appends** — zero or more files from `prompts/append/`, each appended **after** the base (never spliced into the middle). Include `prompts/append/adversarial.md` when the user asks for adversarial / hostile / red-team / attack-style review.
3. **Task block** — short concrete scope last: paths, base ref, constraints, and “do not modify files” when the profile is read-only.

Write the assembled text to a temp file. Prefer that file (or stdin) over a giant shell argument.

Completion: one temp prompt file exists and contains base → appends → task in that order.

### 4. Run Pi

From the repo root (or an agreed worktree for `implement`):

```bash
pi \
  --print \
  --provider <provider.yaml> \
  --model <provider.yaml> \
  --thinking <provider.yaml> \
  --no-session \
  --no-extensions \
  --no-skills \
  --no-prompt-templates \
  --no-context-files \
  --no-approve \
  <profile tools flag> \
  [@files...] \
  <prompt via stdin or @prompt-file>
```

**CLI rules (avoid the failure modes that broke the first run):**

- **PowerShell:** never pass a bare `@path` (splat). Quote every attachment: `'@README.md'`. For the assembled prompt, use stdin (`Get-Content $promptFile -Raw | pi ...`) or a quoted path built as `('@{0}' -f $promptFile)`.
- **bash:** `pi ... @"$promptFile"` or stdin pipe is fine.
- Attach repo context with quoted `@` args when useful; for large diffs use stdin or a temp file.
- For `review` of working-tree changes, pipe a merge-base diff when useful:

```bash
BASE_REF="${BASE_REF:-origin/main}"
MERGE_BASE="$(git merge-base "$BASE_REF" HEAD)"
git diff --no-ext-diff --find-renames --unified=80 "$MERGE_BASE" -- |
  pi ... <same flags> <prompt>
```

For **`verify`**: prefer a disposable git worktree when the tree is already dirty or when bash may rewrite files. Before this step, capture both:

1. `git status --short` (path list / status codes)
2. A **content-level** snapshot of tracked + untracked paths of interest — e.g. `git diff --no-ext-diff` plus hashes (`git hash-object` / checksums) for already-dirty and untracked files you care about

Completion: Pi exited; stdout captured; non-zero exit, empty stdout, auth/model/timeout failures reported to the user without substituting a silent local review.

### 5. Verify the handoff

- Surface Pi's stdout to the user unchanged (summarize only if asked).
- After **`implement`**: run `git status --short`, `git diff --stat`, and relevant tests yourself.
- After **`verify`**:
  - Recapture `git status --short` and content-level diffs/hashes.
  - Report paths that became **newly dirty**, and paths that were **already dirty** whose content changed (status-only comparison misses those).
  - Note the limitation: ignored outputs (`.gitignore`, clean filters, smudge) are not fully covered by status/diff alone — call that out when relevant.
  - Prefer a disposable worktree for verify when practical so side effects never touch the user's working tree.
  - Report Pi's command outcomes; do not claim green without evidence.

Completion: every Pi failure mode is named when it happens; implement and verify side effects are checked in this agent before declaring done.

## Hard rules

- Always pass an explicit tool allowlist (`--tools` or `--no-tools`). Never rely on Pi's default tool set.
- `--tools` is a model allowlist, not an OS sandbox. Presence of `bash` means treat the run as writable.
- Do not co-edit the same working tree: either Cursor investigates while Pi reviews read-only, or Cursor waits while Pi implements (prefer a dedicated git worktree for parallel work).
- Do not ask Pi to `git commit`, `git push`, or open a PR.
- Do not put secrets, API keys, or `.env` contents into the prompt.
- Prefer the `defaults:` isolation flags in `profiles.yaml` for second-opinion runs. Pass reviewed rule files with `@path` instead of loading ambient `AGENTS.md` / `CLAUDE.md`.
- When extending review styles, add a new file under `prompts/append/` and append it after the base template — do not fork `prompts/review.md` for each lens.

## Anago

When Anago's `reviewer` agent requests a Pi second opinion, follow `catalog/skills/anago/review-pi-second-opinion` and only run if Anago review config has `delegatePi.enabled: true` (or legacy `piCodex.enabled: true` when `delegatePi` is absent). Prefer Anago `piCodex.modelSpec` when present.
