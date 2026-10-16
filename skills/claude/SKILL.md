---
name: claude
description: Run or resume Claude Code CLI in Herdr panes or non-interactively for delegated implementation, review, verification, or CLI diagnosis.
---

# Claude Code CLI

Operate Claude Code as a child coding agent through Herdr when explicitly requested, otherwise through Hermes `terminal` and `process` tools. Task content comes from the current user request; this skill defines only CLI execution and safety.

Before ordinary work, load [harness-sessions](../harness-sessions/SKILL.md) to select and protect local history. Use the calling harness directory (for example `.hermes` when Hermes delegates to claude); use workspace-local `.claude` when Claude Code itself is the caller. Write the caller-owned record at dispatch and at completion/handoff (plus real blockers), not every turn. Follow the orchestrator budget in harness-sessions: the worker explores, reads, edits, and tests; the orchestrator dispatches, waits, and reads the worker's summary.

## Readiness

```text
terminal(command="claude --version")
terminal(command="claude auth status --text")
```

Use `claude doctor` when installation or settings health is suspect. Login (`claude auth login`, `claude setup-token`) is interactive and user-owned; stop rather than guessing credentials.

Completion: the binary and auth checks succeed before a provider-backed run.

## Herdr Runs

When the user requests Claude Code through Herdr, this path takes precedence over non-interactive delegation. Load the `herdr` skill and verify `HERDR_ENV=1` before controlling panes. If unavailable, report the blocker; do not silently fall back to a detached `terminal` run. Merely running inside Herdr does not select this path without a user request.

Follow the Herdr skill's layout discovery and direction rule. Default to a sibling pane in the current tab, preserve the caller's cwd and focus, and do not create a workspace or worktree unless requested. For a wide caller pane:

```text
herdr pane split --current --direction right --cwd "$PWD" --no-focus
herdr agent start <unique-name> --kind claude --pane <returned-pane-id> -- --session-id <new-uuid> <permission flags>
herdr agent prompt <unique-name> '<task>' --wait --timeout 600000
herdr agent read <unique-name> --source recent-unwrapped --lines 120
```

Read `<returned-pane-id>` from `.result.pane.pane_id`; `agent start` does not create a pane. Generate and record `<new-uuid>` before launch, and resolve permission flags below. Start Claude Code without an initial task argument, wait for interactive readiness, then submit through `agent prompt`. Herdr supplies the pane's PTY. Keep `--print`, `-p`, `--output-format`, `--permission-prompts`, and `--bg` off this route: it needs the foreground interactive UI, not print output or a detached Claude-managed session. Inspect startup trust or approval dialogs with `agent get` and `agent read`; ask the user before answering them.

For follow-ups, prompt the same verified live agent. To restart a recorded conversation, replace `--session-id <new-uuid>` with `--resume <SESSION_ID>` after `--` in `agent start`, using the recorded cwd and current permission flags. Herdr names and pane IDs locate the live worker; they do not replace Claude's native session ID. Verify the ID from Herdr session metadata when available, otherwise from supported Claude session metadata.

Allow at least 600000 ms (10 minutes) for each completion wait, including every continued `herdr agent wait <unique-name> --timeout 600000`. Run the long `herdr agent prompt ... --wait --timeout 600000` and every `herdr agent wait <unique-name> --timeout 600000` via `terminal(background=true, notify_on_complete=true)` from the start; never run them in the foreground under a shorter tool timeout, and do not poll in between. Wake on the completion notification. On a blocked, stalled, or timed-out wait, inspect `herdr agent get` and `herdr agent read`, then continue, advise, or interrupt from that evidence. Timeout alone does not stop the worker, close the pane, or resubmit, and it does not switch the run to print mode. A completed turn leaves Claude Code running for further interaction; process exit is not required to prove completion.

## Non-Interactive Runs

Only when Herdr was not requested, use `--print` with the target repository as the working directory. Claude Code has no workspace flag: the process cwd is the workspace and the key for its native sessions.

```text
terminal(
  command="claude --print --session-id <new-uuid> --output-format json <permission flags> '<task>'",
  workdir="/absolute/project/path",
  timeout=300,
)
```

Generate `<new-uuid>` before launch and write it to the history record at dispatch; the ID is then known even if the run is interrupted. Print mode skips the workspace trust dialog, so run it only in a workspace the user has authorized.

For both Herdr and non-interactive runs, keep configured CLAUDE.md, skills, hooks, plugins, and MCP servers loaded. Reserve `--bare`, `--safe-mode`, `--setting-sources`, and `--strict-mcp-config` for an explicitly requested isolation or a diagnostic run; `--bare` also ignores OAuth login and requires `ANTHROPIC_API_KEY`. Confirm supported flags with the installed `claude --help`.

## Permission Flags

Always pass `--permission-mode`. Without it the user's `defaultMode` setting applies (for example `auto`), which can run shell commands the delegated task never authorized. Choose the narrowest tier that can complete the task:

```text
# Read-only inspection
--tools "Read,Grep,Glob" --permission-mode dontAsk

# Build/test verification; technically writable because shell commands run
--tools "Read,Grep,Glob,Bash" --permission-mode dontAsk --allowed-tools "Bash(<command prefix>*)"

# User-requested implementation in Herdr (interactive approvals)
--tools default --permission-mode acceptEdits --allowed-tools "Bash(<command prefix>*)"

# User-requested implementation in print mode (deny unapproved calls)
--tools default --permission-mode acceptEdits --permission-prompts none --allowed-tools "Bash(<command prefix>*)"

# Supplied material only
--tools "" --permission-mode dontAsk
```

`dontAsk` denies every call outside the allow rules. `acceptEdits` approves file edits in the workspace; in Herdr, other unapproved calls can show an interactive permission dialog. Inspect it and ask the user before answering; do not broaden the allowlist merely to clear a blocked state. `--permission-prompts none` is print-only and denies those calls instead. Allow rules match the whole command: a redirect or chained command falls outside `Bash(echo *)`. On Windows add `PowerShell` beside `Bash` in `--tools` and the allow rules when the task needs native shell commands. Treat every run with Bash, PowerShell, Write, Edit, hooks, or write-capable MCP tools as writable. One agent owns a writable workspace at a time.

`--permission-mode bypassPermissions` and `--dangerously-skip-permissions` remove the safety boundary; use them only when the user explicitly accepts that risk for an isolated sandbox.

## Model and Budget

Use the configured default unless the user chooses:

```text
--model <alias-or-full-name> --effort <low|medium|high|xhigh|max> --fallback-model <model>
```

`--max-budget-usd <amount>` caps spend for a print run; set it when the user gives a budget. It does not cap an interactive Herdr run. If a hard budget is required with Herdr, explain the limitation and agree on an execution path before launching. Never pass secrets on the command line.

## Input and Output

For non-interactive runs, pipe long or quote-heavy task text through stdin:

```text
terminal(command="claude --print --session-id <new-uuid> --output-format json <permission flags> < /absolute/task.txt", workdir="/project")
```

Reference files and images by absolute path inside the task; Claude Code reads them with its own `Read` tool, so `Read` must be in `--tools`. `--add-dir <dir>` grants file-tool access outside the workspace; add it only when the task requires that directory.

The following output controls are for print runs. For Herdr, read the interactive response through `agent read` instead.

- `--output-format text` — final message only
- `--output-format json` — one result object: check `is_error`, `subtype`, `result`, `session_id`, `permission_denials`, `total_cost_usd`
- `--output-format stream-json --verbose` — JSONL event stream; print mode rejects `stream-json` without `--verbose`
- `--json-schema '<schema>'` — validate a structured final answer

## Sessions and Background Runs

Native sessions live in Claude Code's global store keyed by the workspace path; the workspace-local record is the durable lookup and summary. Do not redirect `CLAUDE_CONFIG_DIR` or copy credentials to make history local.

For a matching prior task outside Herdr, resume the recorded ID from the recorded absolute workspace, passing the current permission flags again because they are per-invocation:

```text
terminal(command="claude --print --resume <SESSION_ID> --output-format json <permission flags> '<follow-up>'", workdir="/project")
```

Confirm the returned `session_id` equals the recorded one. For Herdr, use the live-agent or explicit-resume procedure above. Add `--fork-session` only to branch a conversation deliberately, then record the new ID with its predecessor. Avoid `--continue` and the interactive `--resume` picker. Reserve the print-only `--no-session-persistence` for disposable smoke checks or an explicit no-history request. If the session cannot be resumed, follow harness-sessions to reconstruct context in a new session.

For long non-interactive work, use `terminal(background=true, notify=true)` and inspect it with `process`. For Herdr work, use the background `agent wait` above, then `agent get` and `agent read` in the existing pane. Treat tool wait expiration as a reason to inspect progress, not to kill or relaunch the worker. Record the outcome and next action before handoff.

Interactive Claude Code outside Herdr requires `terminal(background=true, pty=true)`; this is not a substitute for a requested Herdr pane. The CLI's own `--bg` sessions are managed by `claude agents`, `logs`, and `stop`, outside the Herdr and `terminal`/`process` lifecycles.

## Workspace Safety

Set the Herdr pane cwd or Hermes `workdir` to the resolved absolute workspace. Treat hooks, formatters, tests, build commands, and `--worktree` as writable side effects.

For writable runs, the worker captures the baseline (`git status --short`, content diffs/hashes) before editing and reports its diff and tests afterward. A worktree based on `HEAD` omits dirty tracked and untracked state; have the worker reproduce and hash-verify that state before using the worktree, or run in place with explicit side-effect monitoring.

Keep commits, pushes, PR creation, and credential access within the user's authorized scope. Reuse existing authorization; ask only when an action extends it.

## Verification

Ask the worker to return a compact result (a few lines of JSON or bullets): changed paths, test commands with exit codes, blockers, native session ID, and a short summary. After every run:

1. For non-interactive runs, check the exit status; for JSON output confirm `is_error` is false and `subtype` is `success`, and for stream-json confirm a terminal `result` event. For Herdr runs, verify the pane hosts Claude Code and the turn completed, then read its result; `blocked` or `unknown` is not completion, and idle/done alone is not task success.
2. Check `permission_denials` in print JSON, or denied and pending tool calls reported in the Herdr result: a denial means part of the task did not run, even when the result text sounds complete.
3. Retain Claude Code's actual output; do not replace a failed run with an unannounced local answer.
4. Verify from the worker's compact result and exit codes. Spot-check only when risk warrants (for example `git status --short` or one `git diff --stat`); do not re-read full output or files the worker already verified. Ask the worker to fetch missing evidence.
5. Report model, permission mode, tools, workspace, cost when exposed by the selected route, and any incomplete checks.

Completion: process success (non-interactive) or verified turn completion in the Claude Code pane (Herdr), requested evidence, workspace side effects, and a saved continuity record are accounted for.

## Pitfalls

- PowerShell comma-separated tool lists must be one quoted argument.
- Settings files that fail validation are silently ignored in print mode; run `claude doctor` when configured behavior is missing.
- `--allow-dangerously-skip-permissions` only makes bypass selectable; it still widens what the session can reach.
