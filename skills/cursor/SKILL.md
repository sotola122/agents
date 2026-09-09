---
name: cursor
description: Operate Cursor Agent CLI for coding and inspection.
---

# Cursor Agent CLI

Operate Cursor Agent through an interactive Herdr TUI for Big Bang or user-visible pane work; use non-interactive runs only for explicitly headless tasks and bounded smoke checks. Keep task content in the current request; this skill covers only CLI behavior, permissions, workspaces, and verification.

## When to Use

- The user explicitly asks to run or delegate work to Cursor Agent
- A bounded coding or inspection task needs Cursor's CLI
- Cursor authentication, model access, modes, worktrees, or output needs checking

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
herdr agent start <unique-name> --kind cursor --pane <returned-pane-id> -- --sandbox enabled --trust --workspace <absolute-path> --model <verified-model-id>
herdr agent prompt <unique-name> '<task>' --wait --timeout 120000
```

Apply the permission and read-only mode rules below to native startup arguments. Do not pass `--print` / `-p` or print-only output flags. Stream-JSON displays protocol events, not the interactive TUI. Inspect blocked or stalled runs before sending more input; never silently fall back to headless execution. Send follow-ups to the same live agent. The TUI exposes only the reasoning/status and edits that Cursor itself displays; do not promise access to hidden reasoning.

## Non-Interactive Runs

For explicitly headless tasks, use `--print`, pin the absolute workspace, and enable Cursor's sandbox explicitly:

```text
terminal(
  command="agent --print --sandbox enabled --trust --workspace /absolute/project/path '<task>'",
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
- `--continue` — continue the latest conversation
- `--resume [chatId]` — resume a selected conversation

Use text for a simple handoff and JSON/stream-JSON when terminal events or machine parsing are required.

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

Capture `git status --short` plus content-level diffs/hashes before writable runs, and compare them afterward. Cursor must not commit, push, open a PR, or access credentials unless the user separately requests and authorizes that action.

## Verification

After every run:

1. For headless runs, check process exit status and retain actual stdout/stderr. For interactive runs, inspect the completed response through Herdr; idle/done alone is not task success, and the process need not exit.
2. When using headless JSON output, confirm a terminal completion event.
3. For writable runs, inspect repository status, content diff, and relevant tests.
4. Report model, mode, sandbox, workspace, and any incomplete checks.

Completion: process success and every workspace side effect are accounted for.

## Pitfalls

- `--trust` can create workspace-local Cursor runtime files.
- `--sandbox disabled` removes the CLI sandbox override; avoid it.
- Cursor-managed worktree setup scripts can write files; use `--skip-worktree-setup` only when intentionally bypassing them.
- `--approve-mcps` approves every configured MCP server for the run; use it only when explicitly required.