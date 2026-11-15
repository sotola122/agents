---
name: omp
description: Run or resume Oh My Pi (omp) CLI for delegated coding, inspection, verification, or CLI diagnosis, including explicitly requested Herdr panes.
---

# OMP CLI

Operate Oh My Pi as a child coding agent through Herdr when explicitly requested, otherwise through the caller's process tools (Hermes: `terminal` and `process`). Task content comes from the current user request; this skill defines CLI execution, continuity, and safety.

Before ordinary work, load [harness-sessions](../harness-sessions/SKILL.md). Use the calling harness directory (for example `.hermes` when Hermes delegates to omp); use workspace-local `.omp` when OMP itself is the caller. Resolve a conversation-specific `<absolute-history-dir>` under the Git-ignored `agent-sessions/omp/` area. Follow the shared dispatch, completion, and orchestrator-budget rules.

## Readiness

```sh
omp --version
omp --help
omp models --help
omp models find <model-pattern>
```

Use the installed help as the option authority; OMP and Pi are different CLIs. Model listing establishes local availability, not successful provider connectivity. Use the configured model unless the user requests an override. If credentials are missing or rejected, report the blocker; `omp login [provider]` is interactive and user-owned. `omp auth` exports/imports credentials and `omp token` reveals credentials: neither is an auth-status check.

Completion: the binary is identified, required options are supported, and the intended model is available. Report connectivity as unverified until a provider-backed run succeeds.

## Herdr Runs

Only when the user requests Herdr, load the `herdr` skill and verify `HERDR_ENV=1`. If unavailable, report the blocker rather than substituting a detached process. Merely running inside Herdr does not select this route.

Create an owned sibling pane according to the Herdr skill's layout rule, keeping the target cwd and caller focus. For a wide caller pane:

```text
herdr pane split --current --direction right --cwd <absolute-workspace> --no-focus
herdr agent start <unique-name> --kind omp --pane <returned-pane-id> -- --cwd <absolute-workspace> --session-dir <absolute-history-dir>/native <tool flags>
herdr agent prompt <unique-name> '<task>' --wait --timeout 600000
herdr agent read <unique-name> --source recent-unwrapped --lines 120
```

Take the pane ID from the split response; `agent start` does not create layout. Start the interactive UI without an initial task, verify readiness, then submit through `agent prompt`. Keep `--print`, `--mode json`, and RPC modes off this route. Herdr supplies the PTY. Inspect any trust or approval dialog and obtain authorization before answering it.

Send follow-ups to the same verified live agent. For a restart, add `--resume <absolute-session-file>` to native startup arguments, retaining the workspace, history directory, and current tool flags. Herdr names and pane IDs are live handles, not native session IDs.

Allow at least 600000 ms for each completion wait. With Hermes, run long `herdr agent prompt ... --wait --timeout 600000` and `herdr agent wait <unique-name> --timeout 600000` commands through `terminal(background=true, notify_on_complete=true)` from the start; wait for notification rather than polling. With native Herdr tools, use their lifecycle waits. On timeout or a blocked state, inspect `agent get` and `agent read`, then continue, advise, or interrupt based on evidence. Timeout alone does not authorize a relaunch, duplicate prompt, pane closure, or switch to print mode.

## Non-Interactive Runs

When Herdr was not requested, use print mode with an explicit absolute workspace and persistent history:

```text
terminal(
  command="omp --print --cwd <absolute-workspace> --session-dir <absolute-history-dir>/native <tool flags> '<task>'",
  workdir="<absolute-workspace>",
  timeout=300,
)
```

Use the caller's equivalent process tool outside Hermes. For long work, launch in the background and wait for completion notification. Inspect progress after a wait timeout; it does not prove the child failed. Direct interactive runs require a PTY and are not a substitute for a requested Herdr pane.

Keep configured skills, context files, rules, extensions, and plugins enabled for ordinary authorized work. Resource-disabling flags belong to an agreed isolation or diagnostic run. Preserve history independently of resource loading; avoid changing `PI_CODING_AGENT_DIR` or creating a profile merely to relocate sessions, because that also changes other agent state.

## Tool Scope

Choose the smallest built-in tool set that serves the task:

```text
# Inspection; suppress LSP formatting and diagnostics side effects
--tools read,grep,glob --no-lsp

# Build/test verification; writable because bash is available
--tools read,grep,glob,bash

# User-requested implementation
--tools read,grep,glob,bash,edit,write

# Supplied material only; disables built-in tools
--no-tools
```

These are tool-selection flags, not an OS sandbox or a complete capability boundary. In OMP, extensions/custom tools and some settings-managed tools may remain active despite `--tools` or `--no-tools`; hooks can also have side effects. Inspect the effective configuration when restrictions matter. For strict read-only or no-tool requirements, agree on an isolated setup that removes ambient capabilities instead of claiming these flags enforce the boundary.

Add `task`, `eval`, MCP, or extension tools only when needed and authorized. Treat shell execution, eval, subagents, file edits, formatting, and write-capable integrations as writable. One agent owns a writable workspace at a time.

## Model, Input, and Output

Use an exact model from `omp models` when overriding the default:

```text
--model <provider/model-id> --thinking <supported-level>
```

Keep an existing named profile consistent across discovery, launch, and resume. Credentials stay in the supported auth store or environment, not command arguments or history records.

Attach files with absolute `@` paths; this is a print-mode example, not an interactive Herdr launch:

```text
omp --print --cwd <absolute-workspace> --session-dir <absolute-history-dir>/native <tool flags> @/absolute/task.md '<task>'
```

Preflight attachment paths. Supported images become vision input; confirm handling before treating PDFs or other binary formats as readable attachments.

- `--mode text` (default): final text response.
- `--mode json`: JSONL session header and agent events; capture stderr separately.
- `--wait-async`: in print mode, wait for background jobs and feed their results back before exit. Use when the task depends on those jobs, not merely on their launch.
- `--max-time <duration>`: an intentional run deadline, distinct from a tool's wait timeout; use when the request calls for a bounded runtime.

## Session Continuity

Capture the actual native session ID and file from OMP metadata. JSON mode emits a session header; match it to the saved file under the selected native directory and verify the workspace. Save both in the caller-owned record without modifying OMP's native contents.

Resume a recorded conversation explicitly:

```text
omp --print --cwd <recorded-workspace> --session-dir <absolute-history-dir>/native --resume <absolute-session-file> <current-tool-flags> '<follow-up>'
```

`--resume` also accepts an ID prefix, but the verified absolute file avoids ambiguous matches. Avoid `--continue` and an unqualified resume picker for recorded work. Use `--restore <absolute-session-file>` only when intentionally recovering interrupted execution: unlike ordinary resume, it can restart the unfinished turn and subagents. Confirm the original worker has stopped and recheck side effects before recovery.

Reserve `--no-session` for disposable smoke checks or an explicit no-history request. If native history is missing or incompatible, follow harness-sessions to reconstruct context and record the limitation. Keep history after process or pane cleanup.

## Workspace Safety

Set the pane/process cwd and `--cwd` to the same resolved workspace. For writable work, have the worker capture the baseline (`git status --short` and content diffs/hashes), then report changed paths and tests. A worktree created from `HEAD` omits dirty tracked and untracked state; reproduce and hash-verify that state or work in place with side-effect monitoring.

Keep commits, pushes, PR creation, and credential access within the user's authorized scope. A resumed session inherits context, not broader permission.

## Verification

Ask the worker for a compact result: changed paths, test commands with exit codes, blockers, native session ID/file, and a short summary.

1. For print runs, check process exit status and retain actual output. In JSON mode, require the completed `agent_end` event and inspect the final assistant message for an error/abort stop reason; an end event alone does not prove success.
2. For Herdr, verify the pane hosts OMP and read the completed response. `blocked` or `unknown` requires inspection; idle/done alone is not task success. The interactive process can remain alive.
3. Account for failed tools, unfinished background jobs, and workspace side effects using the worker's evidence. Ask for missing evidence; spot-check only where risk warrants, rather than repeating the worker's investigation.
4. Save the continuity record and report the actual provider/model, workspace, tool scope, and incomplete checks. Preserve a failed worker result instead of silently replacing it with a local answer.

Completion: the requested outcome, execution status, verification evidence, side effects, and resumable history are all accounted for.
