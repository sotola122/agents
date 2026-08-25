---
name: codex
description: >-
  Delegate bounded review, verification, implementation, or smoke checks to
  the Codex CLI (`codex review` / `codex exec`).
---

# Codex CLI Delegation

Hand one bounded task to Codex as a child agent. Prefer non-interactive
`codex review` / `codex exec`. Do not start the interactive TUI for delegation.

Prompt bodies live under [`prompts/`](prompts/). Sandbox mapping is in
[`profiles.yaml`](profiles.yaml).

## Steps

### 0. Smoke (only when asked)

When the user asks to smoke-test or confirm Codex auth / model / connectivity — and only then — run this step before (or instead of) a real task. Otherwise skip to step 1.

1. Read [profiles.yaml](profiles.yaml) → use the `smoke` profile (`sandbox: read-only`).
2. Run with the body of [`prompts/smoke.md`](prompts/smoke.md).

```bash
codex exec \
  --sandbox read-only \
  [-m <model if user named one>] \
  -
```

(`smoke` / `verify` / `implement` use `exec`, so `-m` is valid here.)

Pipe the smoke prompt via stdin (`codex exec ... -`). Completion: skipped (user did not ask), or stdout is exactly `OK` (trim whitespace) and exit code is 0. On any other smoke outcome (non-zero, empty, wrong text, auth/model error), **stop** and report the failure — do not run the real task.

### 1. Choose a permission profile

Read [profiles.yaml](profiles.yaml). Pick **exactly one** profile that matches the task:

| Task | Profile |
| --- | --- |
| Review, design check, static bug hunt | `review` |
| Build, test, lint, reproduce (no source edits intended) | `verify` |
| Implement, fix, refactor (user explicitly asked) | `implement` |

Map the profile to the CLI:

- `command: review` → `codex review`
- `command: exec` → `codex exec`
- `sandbox: …` → `--sandbox …` on `exec`; on `review`, pass `-c sandbox_mode="<value>"` so a permissive user config cannot widen the run

Completion: the profile name, command, and sandbox are fixed. Do not invent sandbox modes.

### 2. Resolve model (optional)

Pass a model override only when the user names a model. Otherwise omit it and use `~/.codex/config.toml`.

- `codex exec` → `-m <model>`
- `codex review` → `-c model="<model>"` (`review` has no `-m` flag)

Completion: the correct override for the chosen command is set, or both are omitted.

### 3. Assemble the prompt

Build one prompt file by concatenating, in order:

1. **Base** — `prompts/<profile>.md` when it exists (`verify`, `implement`). For `review`, skip base — `codex review` owns the review skeleton.
2. **Appends** — zero or more files from `prompts/append/`, each appended **after** the base (never spliced into the middle). Include `prompts/append/adversarial.md` when the user asks for adversarial / hostile / red-team / attack-style review.
3. **Task block** — short concrete scope last: paths, base ref, constraints, and “do not modify files” when the profile is read-only.

Write the assembled text to a temp file. Prefer that file (or stdin) over a giant shell argument.

**Review prompt rule:** Codex CLI rejects combining a custom `[PROMPT]` (including `-` for stdin) with `--uncommitted` / `--base` / `--commit`. Choose exactly one review mode in step 4.

Completion: for `verify` / `implement`, one temp prompt file exists (base → appends → task). For `review` scope mode, no custom prompt file is required. For `review` custom mode, the temp file holds appends → task only.

### 4. Run Codex

From the repo root (or an agreed worktree for `implement`):

**Review — scope mode** (default when the user wants working-tree / branch / commit review and no custom lens):

```bash
codex review \
  -c sandbox_mode="read-only" \
  [-c model="<model if user named one>"] \
  [--uncommitted | --base <branch> | --commit <sha>]
```

Pick one scope flag: working-tree → `--uncommitted`; vs a branch → `--base`; a single commit → `--commit`. Do **not** pass a prompt argument or `-`. Do **not** pass `-m` to `review`.

**Review — custom mode** (when appends / adversarial / extra instructions are required):

```bash
codex review \
  -c sandbox_mode="read-only" \
  [-c model="<model if user named one>"] \
  -
```

Omit all scope flags. Pipe the assembled prompt on stdin. If a diff is needed, include it in the prompt file (or use prompt-plus-stdin with `codex exec` instead).

**Verify / implement:**

```bash
codex exec \
  --sandbox <profiles.yaml sandbox> \
  [-m <model if user named one>] \
  -
```

**CLI rules:**

- **PowerShell:** pipe with `Get-Content $promptFile -Raw | codex … -`. For `-c`, prefer `-c 'sandbox_mode="read-only"'` (quoted) so the shell does not strip the inner quotes.
- **bash:** `codex … - <"$promptFile"` or stdin pipe is fine; `-c sandbox_mode="read-only"` is fine.
- For large diffs as extra context with `exec`, pipe them as stdin alongside a prompt argument (Codex appends piped stdin as a `<stdin>` block) or fold them into the assembled prompt file.
- Progress goes to stderr; the final agent message goes to stdout — capture stdout for the handoff.

For **`verify`**: prefer a disposable git worktree when the tree is already dirty or when commands may rewrite files. Before this step, capture both:

1. `git status --short` (path list / status codes)
2. A **content-level** snapshot of tracked + untracked paths of interest — e.g. `git diff --no-ext-diff` plus hashes (`git hash-object` / checksums) for already-dirty and untracked files you care about

Completion: Codex exited; stdout captured; non-zero exit, empty stdout, auth/model/timeout failures reported to the user without substituting a silent local review.

### 5. Verify the handoff

- Surface Codex's stdout to the user unchanged (summarize only if asked).
- After **`implement`**: run `git status --short`, `git diff --stat`, and relevant tests yourself.
- After **`verify`**:
  - Recapture `git status --short` and content-level diffs/hashes.
  - Report paths that became **newly dirty**, and paths that were **already dirty** whose content changed (status-only comparison misses those).
  - Note the limitation: ignored outputs (`.gitignore`, clean filters, smudge) are not fully covered by status/diff alone — call that out when relevant.
  - Prefer a disposable worktree for verify when practical so side effects never touch the user's working tree.
  - Report Codex's command outcomes; do not claim green without evidence.

Completion: every Codex failure mode is named when it happens; implement and verify side effects are checked in this agent before declaring done.

## Hard rules

- Always pass an explicit sandbox (`--sandbox` on `exec`, or `-c sandbox_mode=…` on `review`). Never rely on the user's default sandbox alone.
- Do not co-edit the same working tree: either Cursor investigates while Codex reviews read-only, or Cursor waits while Codex implements (prefer a dedicated git worktree for parallel work).
- Do not ask Codex to `git commit`, `git push`, or open a PR.
- Do not put secrets, API keys, or `.env` contents into the prompt.
- When extending review styles, add a new file under `prompts/append/` and append it after any base template — do not fork a full review skeleton for each lens.

## Anago

When Anago's `reviewer` agent requests a Codex second opinion, only run if Anago review config has `delegateCodex.enabled: true`.
