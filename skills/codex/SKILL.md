---
name: codex
description: Run or resume Codex CLI for delegated implementation, review, verification, or CLI diagnosis.
---

# Codex CLI

Operate Codex non-interactively through Hermes `terminal` and `process` tools. Task content comes from the current user request; this skill defines only CLI execution and safety.

Before ordinary work, load [harness-sessions](../harness-sessions/SKILL.md) to select and protect local history. Use the calling harness directory (for example `.hermes` when Hermes delegates to codex); use workspace-local `.codex` when codex itself is the caller. Keep normal conversations persistent and checkpoint the caller-owned record after each turn or blocker.

## Readiness

```text
terminal(command="codex --version")
terminal(command="codex login status")
```

Use `codex doctor` when installation or runtime health is suspect. Authentication setup is interactive and user-owned; stop rather than guessing credentials.

Completion: the binary and login checks succeed before a provider-backed run.

## Non-Interactive Execution

Use `codex exec` with an explicit workspace and sandbox:

```text
terminal(
  command="codex exec --sandbox <mode> -C /absolute/project/path '<task>'",
  workdir="/absolute/project/path",
  timeout=300,
)
```

Sandbox modes:

- `read-only` — inspection only
- `workspace-write` — implementation or commands that may write under the workspace
- `danger-full-access` — avoid unless the user explicitly accepts the risk

`--sandbox` is the technical boundary; prose requesting no edits is not one. Reserve `--ephemeral` for disposable smoke checks or an explicit no-history request; ordinary delegated work must remain resumable.

## Model and Configuration

- `-m <model>` — model override for `exec`
- `-c key=value` — one invocation-specific config override
- `-p <profile>` — layer a named Codex config profile
- `--strict-config` — reject unknown configuration keys
- `--ignore-user-config` — skip user config while retaining authentication

Omit model/config overrides when the configured defaults are intended. Never pass secrets as command-line config values.

## Code Review

`codex review` supports one built-in scope at a time:

```text
terminal(command="codex review -c sandbox_mode=\"read-only\" --uncommitted", workdir="/project")
terminal(command="codex review -c sandbox_mode=\"read-only\" --base <branch>", workdir="/project")
terminal(command="codex review -c sandbox_mode=\"read-only\" --commit <sha>", workdir="/project")
```

Do not combine a custom task argument with `--uncommitted`, `--base`, or `--commit`; the CLI rejects that combination. `review` uses `-c model="<model>"` for model override rather than `-m`.

## Input and Output

Use `-` to read task text from stdin when shell quoting or size makes an argument unsuitable:

```text
terminal(command="codex exec --sandbox read-only -C /project - < /absolute/task.txt")
```

The following controls are `codex exec` only; `codex review` does not accept them in the installed CLI:

- `--json` — JSONL event output
- `-o <file>` / `--output-last-message <file>` — save only the final message
- `--color never` — stable non-interactive logs
- `-i <file>...` — attach images

Progress is written to stderr; the final response is written to stdout. Capture them separately when exact stdout matters.

## Sessions and Background Runs

Capture the native session ID from actual CLI/session output; when using `--json`, read the `thread_id` from the thread-start event. Save the ID with the workspace, scope, decisions, and evidence in the caller-owned history. Native rollout files may remain in Codex's supported global store; the workspace-local record is the durable lookup and summary. Do not redirect `CODEX_HOME` or copy authentication to make history local.

For a matching prior task, run `codex exec resume <SESSION_ID> '<follow-up>'` from the recorded absolute workspace. Check `codex exec resume --help` and explicitly retain the currently authorized sandbox, model, and working-directory settings using supported option placement; `exec` and `exec resume` options can differ. Avoid `--last` and cross-workspace selection. If the native session cannot be resumed, follow harness-sessions to reconstruct context in a new session.

Record standalone `codex review` results as history even if that command exposes no resumable ID; mark native resumption unavailable instead of fabricating an ID. A follow-up can receive that recorded review as context in `exec`.

For long work, use `terminal(background=true, notify_on_complete=true)` and inspect it with `process`. Treat tool wait expiration as a reason to inspect progress, not to kill or relaunch the worker. Record the outcome and next action before handoff.

Interactive Codex requires `pty=true`; prefer `exec` or `review` for delegation.

## Workspace Safety

Set both Hermes `workdir` and Codex `-C` to the resolved absolute workspace. Treat `workspace-write`, hooks, formatters, tests, and build commands as writable.

Before a writable run, capture `git status --short` plus content-level diffs/hashes. A worktree based on `HEAD` omits dirty tracked and untracked state; reproduce and hash-verify that state before delegating against the worktree.

Keep commits, pushes, PR creation, and credential access within the user's authorized scope. Reuse existing authorization; ask only when an action extends it.

## Verification

After every run:

1. Check exit status and retain Codex's actual stdout/stderr.
2. For JSONL, confirm the stream reaches a terminal success event.
3. For writable runs, inspect repository status, content diff, and relevant tests.
4. Report model, sandbox, workspace, and any incomplete checks.

Completion: process success, requested evidence, workspace side effects, and a saved continuity record are accounted for.

## Pitfalls

- `--dangerously-bypass-approvals-and-sandbox` disables the primary safety boundary.
- `--add-dir` grants another writable directory; use it only when required.
- `--skip-git-repo-check` is for intentional non-repository work.
- Hooks can have side effects even when the requested task appears read-only; inspect active configuration when that matters.
