---
name: claude
description: Run or resume Claude Code CLI for delegated implementation, review, verification, or CLI diagnosis.
---

# Claude Code CLI

Operate Claude Code non-interactively through Hermes `terminal` and `process` tools. Task content comes from the current user request; this skill defines only CLI execution and safety.

Before ordinary work, load [harness-sessions](../harness-sessions/SKILL.md) to select and protect local history. Use the calling harness directory (for example `.hermes` when Hermes delegates to claude); use workspace-local `.claude` when Claude Code itself is the caller. Keep normal conversations persistent and checkpoint the caller-owned record after each turn or blocker.

## Readiness

```text
terminal(command="claude --version")
terminal(command="claude auth status --text")
```

Use `claude doctor` when installation or settings health is suspect. Login (`claude auth login`, `claude setup-token`) is interactive and user-owned; stop rather than guessing credentials.

Completion: the binary and auth checks succeed before a provider-backed run.

## Non-Interactive Execution

Use `--print` with the target repository as the working directory. Claude Code has no workspace flag: the process cwd is the workspace and the key for its native sessions.

```text
terminal(
  command="claude --print --session-id <new-uuid> --output-format json <permission flags> '<task>'",
  workdir="/absolute/project/path",
  timeout=300,
)
```

Generate `<new-uuid>` before launch and write it to the history record at dispatch; the ID is then known even if the run is interrupted. Print mode skips the workspace trust dialog, so run it only in a workspace the user has authorized.

Keep configured CLAUDE.md, skills, hooks, plugins, and MCP servers loaded. Reserve `--bare`, `--safe-mode`, `--setting-sources`, and `--strict-mcp-config` for an explicitly requested isolation or a diagnostic run; `--bare` also ignores OAuth login and requires `ANTHROPIC_API_KEY`.

## Permission Flags

Always pass `--permission-mode`. Without it the user's `defaultMode` setting applies (for example `auto`), which can run shell commands the delegated task never authorized. Choose the narrowest tier that can complete the task:

```text
# Read-only inspection
--tools "Read,Grep,Glob" --permission-mode dontAsk

# Build/test verification; technically writable because shell commands run
--tools "Read,Grep,Glob,Bash" --permission-mode dontAsk --allowed-tools "Bash(<command prefix>*)"

# User-requested implementation
--tools default --permission-mode acceptEdits --permission-prompts none --allowed-tools "Bash(<command prefix>*)"

# Supplied material only
--tools ""
```

`dontAsk` denies every call outside the allow rules; `acceptEdits` with `--permission-prompts none` approves file edits in the workspace and denies other unapproved calls. Allow rules match the whole command: a redirect or chained command falls outside `Bash(echo *)`. On Windows add `PowerShell` beside `Bash` in `--tools` and the allow rules when the task needs native shell commands. Treat every run with Bash, PowerShell, Write, Edit, hooks, or write-capable MCP tools as writable. One agent owns a writable workspace at a time.

`--permission-mode bypassPermissions` and `--dangerously-skip-permissions` remove the safety boundary; use them only when the user explicitly accepts that risk for an isolated sandbox.

## Model and Budget

Use the configured default unless the user chooses:

```text
--model <alias-or-full-name> --effort <low|medium|high|xhigh|max> --fallback-model <model>
```

`--max-budget-usd <amount>` caps spend for a print run; set it when the user gives a budget. Never pass secrets on the command line.

## Input and Output

Pipe long or quote-heavy task text through stdin:

```text
terminal(command="claude --print --session-id <new-uuid> --output-format json <permission flags> < /absolute/task.txt", workdir="/project")
```

Reference files and images by absolute path inside the task; Claude Code reads them with its own `Read` tool, so `Read` must be in `--tools`. `--add-dir <dir>` grants file-tool access outside the workspace; add it only when the task requires that directory.

- `--output-format text` — final message only
- `--output-format json` — one result object: check `is_error`, `subtype`, `result`, `session_id`, `permission_denials`, `total_cost_usd`
- `--output-format stream-json --verbose` — JSONL event stream; print mode rejects `stream-json` without `--verbose`
- `--json-schema '<schema>'` — validate a structured final answer

## Sessions and Background Runs

Native sessions live in Claude Code's global store keyed by the workspace path; the workspace-local record is the durable lookup and summary. Do not redirect `CLAUDE_CONFIG_DIR` or copy credentials to make history local.

For a matching prior task, resume the recorded ID from the recorded absolute workspace, passing the current permission flags again because they are per-invocation:

```text
terminal(command="claude --print --resume <SESSION_ID> --output-format json <permission flags> '<follow-up>'", workdir="/project")
```

Confirm the returned `session_id` equals the recorded one. Add `--fork-session` only to branch a conversation deliberately, then record the new ID with its predecessor. Avoid `--continue` and the interactive `--resume` picker. Reserve `--no-session-persistence` for disposable smoke checks or an explicit no-history request. If the session cannot be resumed, follow harness-sessions to reconstruct context in a new session.

For long work, use `terminal(background=true, notify_on_complete=true)` and inspect it with `process`. Treat tool wait expiration as a reason to inspect progress, not to kill or relaunch the worker. Record the outcome and next action before handoff.

Prefer `--print` for delegation. Interactive Claude Code requires `pty=true`; the CLI's own `--bg` sessions are managed by `claude agents`, `logs`, and `stop`, outside the `terminal`/`process` lifecycle.

## Workspace Safety

Set Hermes `workdir` to the resolved absolute workspace. Treat hooks, formatters, tests, build commands, and `--worktree` as writable side effects.

Before a writable run, capture `git status --short` plus content-level diffs/hashes. A worktree based on `HEAD` omits dirty tracked and untracked state; reproduce and hash-verify that state before delegating against the worktree.

Keep commits, pushes, PR creation, and credential access within the user's authorized scope. Reuse existing authorization; ask only when an action extends it.

## Verification

After every run:

1. Check the exit status; for JSON output confirm `is_error` is false and `subtype` is `success`, and for stream-json confirm a terminal `result` event.
2. Inspect `permission_denials`: a denial means part of the task did not run, even when the result text sounds complete.
3. Retain Claude Code's actual output; do not replace a failed run with an unannounced local answer.
4. For writable runs, inspect repository status, content diff, and relevant tests.
5. Report model, permission mode, tools, workspace, cost, and any incomplete checks.

Completion: process success, requested evidence, workspace side effects, and a saved continuity record are accounted for.

## Pitfalls

- PowerShell comma-separated tool lists must be one quoted argument.
- Settings files that fail validation are silently ignored in print mode; run `claude doctor` when configured behavior is missing.
- `--allow-dangerously-skip-permissions` only makes bypass selectable; it still widens what the session can reach.
