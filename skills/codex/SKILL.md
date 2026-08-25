---
name: codex
description: Operate Codex CLI for coding, review, and verification.
---

# Codex CLI

Operate Codex non-interactively through Hermes `terminal` and `process` tools. Task content comes from the current user request; this skill defines only CLI execution and safety.

## When to Use

- The user explicitly asks to run or delegate work to Codex
- A bounded implementation or verification task needs a separate CLI agent
- A working tree, branch, or commit needs `codex review`
- Codex installation, login, model, sandbox, or output behavior needs checking

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
  command="codex exec --ephemeral --sandbox <mode> -C /absolute/project/path '<task>'",
  workdir="/absolute/project/path",
  timeout=300,
)
```

Sandbox modes:

- `read-only` — inspection only
- `workspace-write` — implementation or commands that may write under the workspace
- `danger-full-access` — avoid unless the user explicitly accepts the risk

`--sandbox` is the technical boundary; prose requesting no edits is not one. Use `--ephemeral` for one-shot work that should not persist a Codex session.

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
terminal(command="codex exec --ephemeral --sandbox read-only -C /project - < /absolute/task.txt")
```

Useful output controls:

- `--json` — JSONL event output
- `-o <file>` / `--output-last-message <file>` — save only the final message
- `--color never` — stable non-interactive logs
- `-i <file>...` — attach images

Progress is written to stderr; the final response is written to stdout. Capture them separately when exact stdout matters.

## Sessions and Background Runs

Use `codex exec resume --last` or a session ID only when continuity is intentional. For long bounded work, use `terminal(background=true, notify_on_complete=true)` and inspect it with `process`.

Interactive Codex requires `pty=true`; prefer `exec` or `review` for delegation.

## Workspace Safety

Set both Hermes `workdir` and Codex `-C` to the resolved absolute workspace. Treat `workspace-write`, hooks, formatters, tests, and build commands as writable.

Before a writable run, capture `git status --short` plus content-level diffs/hashes. A worktree based on `HEAD` omits dirty tracked and untracked state; reproduce and hash-verify that state before delegating against the worktree.

Codex must not commit, push, open a PR, or access credentials unless the user separately requests and authorizes that action.

## Verification

After every run:

1. Check exit status and retain Codex's actual stdout/stderr.
2. For JSONL, confirm the stream reaches a terminal success event.
3. For writable runs, inspect repository status, content diff, and relevant tests.
4. Report model, sandbox, workspace, and any incomplete checks.

Completion: process success and every workspace side effect are accounted for.

## Pitfalls

- `--dangerously-bypass-approvals-and-sandbox` disables the primary safety boundary.
- `--add-dir` grants another writable directory; use it only when required.
- `--skip-git-repo-check` is for intentional non-repository work.
- Hooks can have side effects even when the requested task appears read-only; inspect active configuration when that matters.