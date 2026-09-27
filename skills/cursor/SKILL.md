---
name: cursor
description: Run or resume Cursor Agent CLI for delegated coding, inspection, or CLI diagnosis; use for interactive Herdr panes and explicitly headless tasks.
---

# Cursor Agent CLI

Operate Cursor Agent through an interactive Herdr TUI for Big Bang or user-visible pane work; use non-interactive runs only for explicitly headless tasks and bounded smoke checks. Keep task content in the current request; this skill covers only CLI behavior, permissions, workspaces, and verification.

Before ordinary work, load [harness-sessions](../harness-sessions/SKILL.md) to select and protect local history. Use the calling harness directory (for example `.hermes` when Hermes delegates to cursor); use workspace-local `.cursor` when cursor itself is the caller. Keep normal conversations persistent and checkpoint the caller-owned record after each turn or blocker.

## Readiness

```text
terminal(command="agent --version")
terminal(command="agent status --format text")
terminal(command="agent --list-models")
```

`agent login` is interactive and user-owned. Never type or expose `CURSOR_API_KEY` on the user's behalf.

Completion: the installed binary reports an authenticated account and the requested model is available.

## Interactive Herdr Runs

For Big Bang or user-visible pane work, load `herdr`, verify caller context, and create an owned sibling pane according to that skill. Start the TUI and send work through the agent surface:

```text
herdr agent start <unique-name> --kind cursor --pane <returned-pane-id> -- --sandbox enabled --workspace <absolute-path> --model <verified-model-id> --resume <explicit-chat-id>
herdr agent prompt <unique-name> '<task>' --wait --timeout 600000
```

Resolve the explicit chat ID through the session procedure below before startup. Apply the permission and read-only mode rules below to native arguments. `--trust` is a headless option; inspect any interactive trust UI under the current authorization. Keep print-only flags off the TUI route. Inspect blocked or stalled runs before sending more input; never silently fall back to headless execution. Send follow-ups to the same live agent. The TUI exposes only what Cursor itself displays.

In Big Bang, follow its supervision decisions. For other pane work, likewise allow at least 600000 ms per completion wait, inspect `herdr agent get` and `herdr agent read` on timeout, then continue, advise, or interrupt based on evidence. Timeout alone does not authorize stopping the worker, closing the pane, or resubmitting. Use an outer background/process handle when necessary to keep long waits alive.

## Non-Interactive Runs

For explicitly headless tasks, use `--print`, pin the absolute workspace, and enable Cursor's sandbox explicitly:

```text
terminal(
  command="agent --print --sandbox enabled --trust --workspace /absolute/project/path --resume <explicit-chat-id> '<task>'",
  workdir="/absolute/project/path",
  timeout=300,
)
```

`--print` exits after the run. It can access shell and write tools; without `--force`, actions requiring approval may not proceed in headless mode.

## Read-Only Modes

- `--mode ask` — Q&A and inspection without edits
- `--mode plan` / `--plan` — read-only planning

```text
terminal(command="agent --print --mode ask --sandbox enabled --trust --workspace /project '<task>'")
```

Use read-only modes for review and diagnosis. Omit `--force`.

## Writable Runs

Use `--force` only for user-requested implementation or verification that requires command execution:

```text
terminal(command="agent --print --force --sandbox enabled --trust --workspace /project '<task>'")
```

`--force` auto-allows commands unless explicitly denied. `--yolo` is an alias; prefer the clearer `--force`. One agent owns a writable workspace at a time.

## Models and Output

- `--model <model>` — select a model
- `--output-format text|json|stream-json` — output format in print mode
- `--stream-partial-output` — emit text deltas with `stream-json`
- `--resume <chatId>` — resume the explicitly selected native conversation

Use text for a simple handoff and JSON/stream-JSON when terminal events or machine parsing are required.

## Session continuity

For a matching recorded conversation, pass its verified native ID with `--resume <chatId>` and retain the explicit workspace. For new ordinary work, confirm support with `agent create-chat --help`, run `agent --workspace <absolute-path> create-chat`, capture the returned ID, and save it before launching the task with `--resume`. If unavailable, start normally and obtain the actual ID from supported CLI/session metadata; record the limitation rather than guessing or using the most recent chat.

Herdr names and pane IDs do not replace the native chat ID. Keep Cursor's native session storage in its supported location; the local record stores the ID, decisions, and recovery context. Reuse a live TUI until it needs restarting. At every handoff, update the caller-owned history with the ID, evidence, and next action. Use the reconstruction procedure in harness-sessions if the native session is gone.

## Workspaces and Worktrees

Always pass `--workspace <absolute-path>` for in-place or caller-managed worktrees. Use Cursor-managed isolation only for clean-HEAD tasks:

```text
agent --print --worktree [name] --worktree-base <ref> --sandbox enabled --trust '<task>'
```

Cursor-managed worktrees start from a Git ref and do not include dirty tracked or untracked state. Reproduce and hash-verify dirty state in a caller-managed worktree, or operate in place with explicit side-effect monitoring.

`--add-dir <path>` expands workspace access; grant only paths required by the user request.

## Smoke Checks

Run provider smoke checks in a unique temporary empty workspace because Cursor may create `.cursor/` runtime files:

```text
terminal(command="agent --print --mode ask --sandbox enabled --trust --workspace <temp-dir> '<minimal task>'")
```

Inspect and remove the temporary workspace after the process exits. A successful auth-status check alone does not prove model connectivity.

## Background and Interactive Runs

For a long bounded headless run, use `terminal(background=true, notify=true)` and inspect it with the process tool. Interactive Cursor Agent requires a PTY: Herdr supplies it in managed panes; direct terminal runs require `pty=true` with `background=true`. Big Bang uses the interactive Herdr route above, not print mode.

## Workspace Safety

Capture `git status --short` plus content-level diffs/hashes before writable runs, and compare them afterward. Keep commits, pushes, PR creation, and credential access within the user's authorized scope. Reuse existing authorization; ask only when an action extends it.

## Verification

After every run:

1. For headless runs, check process exit status and retain actual stdout/stderr. For interactive runs, inspect the completed response through Herdr; idle/done alone is not task success, and the process need not exit.
2. When using headless JSON output, confirm a terminal completion event.
3. For writable runs, inspect repository status, content diff, and relevant tests.
4. Report model, mode, sandbox, workspace, and any incomplete checks.

Completion: the requested outcome and workspace side effects are verified, and local history identifies the conversation and its last verified state. For an interactive run, the worker can remain alive.

## Pitfalls

- `--trust` can create workspace-local Cursor runtime files.
- `--sandbox disabled` removes the CLI sandbox override; avoid it.
- Cursor-managed worktree setup scripts can write files; use `--skip-worktree-setup` only when intentionally bypassing them.
- `--approve-mcps` approves every configured MCP server for the run; use it only when explicitly required.
