---
name: cursor
description: >-
  Delegate bounded review, verification, implementation, or smoke checks to
  the Cursor Agent CLI (`agent --print`).
---

# Cursor CLI Delegation

Hand one bounded task to Cursor Agent as a non-interactive child. Use `agent --print`; do not open the interactive TUI for delegation.

Profiles: [`profiles.yaml`](profiles.yaml). Prompt contracts: [`prompts/`](prompts/).

## Steps

### 0. Smoke only when asked

When the user asks to check Cursor authentication, model access, or connectivity, read [`prompts/smoke.md`](prompts/smoke.md) and run:

```bash
agent --print --mode ask --sandbox enabled --trust "Respond with exactly: OK"
```

Completion: skipped when not requested, or exit code is 0 and trimmed stdout is exactly `OK`. On any other result, stop and report the failure without running the real task.

### 1. Choose one permission profile

Read [`profiles.yaml`](profiles.yaml) and select exactly one profile:

| Task | Profile |
| --- | --- |
| Review, design check, static bug hunt | `review` |
| Build, test, lint, reproduce | `verify` |
| Implement, fix, refactor | `implement` |

Apply every profile field:

- `mode: ask` -> `--mode ask`; `mode: agent` -> omit `--mode`
- `sandbox` -> `--sandbox <value>`
- `force: true` -> `--force`; false -> omit it
- Always pass `--trust` for headless workspace trust

`--force` auto-approves tool calls and makes a run shell/file writable. Select `implement` only when the user explicitly requested edits. Treat `verify` as technically writable even though its prompt forbids intentional source edits.

Completion: profile, exact flags, and `writable` state are recorded. Never widen a profile silently.

### 2. Resolve model override

Pass `--model <model>` only when the user names a model. Otherwise omit it and use Cursor's configured default.

Completion: one explicit model is selected or the override is deliberately absent.

### 3. Assemble one prompt

Require `prompts/<profile>.md`. Concatenate in order:

1. Base prompt for the selected profile
2. [`prompts/append/adversarial.md`](prompts/append/adversarial.md) only for an adversarial/hostile/red-team lens
3. Task block containing:

```text
objective:
in_scope:
out_of_scope:
acceptance_checks:  # numbered and independently verifiable
allowed_task_side_effects: none | [explicit list]
workspace: in_place | worktree
stop_conditions:
```

Write the result to a unique UTF-8 temporary file outside the repository. Do not include secrets, API keys, or `.env` contents.

Completion: base -> optional append -> task block exists once, every acceptance check is testable, and no secret is present.

### 4. Choose the workspace

- `review`: use the current repository read-only.
- `verify`: use `agent --worktree` when the tree is dirty or commands may rewrite tracked files; otherwise capture status plus content hashes/diffs before running in place.
- `implement`: do not co-edit a working tree. Use an agreed worktree when work runs in parallel; otherwise the parent waits for Cursor to exit.

Before every writable run, capture `git status --short` and content-level diffs/hashes for already-dirty and untracked paths of interest.

Completion: `workspace` and its isolation reason are in the task block; the pre-run state is captured for writable profiles.

### 5. Run Cursor Agent

From the selected repository/worktree, pass the assembled prompt as one shell argument.

Review:

```bash
agent --print --mode ask --sandbox enabled --trust "$(<"$PROMPT_FILE")"
```

Verify or implement:

```bash
agent --print --force --sandbox enabled --trust "$(<"$PROMPT_FILE")"
```

Add `--model <model>` only when resolved in step 2. For an isolated Cursor-managed worktree, add `--worktree [name]` and record the resulting path. Capture stdout, stderr, and exit code. Do not substitute a local answer when Cursor fails.

Completion: the process exited and all output is captured; nonzero exit, empty stdout, authentication/model errors, and timeouts are reported as delegation failures.

### 6. Verify the handoff

All are required:

1. Exit code is 0.
2. Output begins with the profile heading (`# Review Result`, `# Verify Result`, or `# Implement Result`).
3. Every numbered acceptance check has explicit evidence.
4. Actual side effects are a subset of `allowed_task_side_effects`.

After `verify` or `implement`, recapture `git status --short`, content diffs/hashes, and relevant tests. Report newly dirty paths and changed already-dirty paths. Remove a disposable worktree only after retained evidence or intended edits have been transferred and verified.

Completion: declare success only when all four checks and parent-side verification pass; otherwise report `Delegation incomplete` with the unmet checks.

## Hard rules

- Review and smoke never use `--force`.
- Every run passes `--sandbox enabled` and `--trust` explicitly.
- No Cursor-authored commit, push, PR, credential access, or secret in prompts.
- One child owns a writable working tree at a time.
- Provider-backed smoke runs only when requested.
