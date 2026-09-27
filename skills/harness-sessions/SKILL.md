---
name: harness-sessions
description: Preserve and resume workspace-local CLI agent history. Use before dispatch or resume and at checkpoints in big-bang, cursor, codex, and pi.
---

# Harness sessions

Keep native conversations resumable and a small local record that another orchestrator can use after its own context is lost. The calling CLI skill owns native session syntax; this skill owns storage, selection, and checkpoints. The orchestrator writes history; workers return evidence. Use one record per worker conversation, with one writer.

## 1. Select the local store

Resolve the absolute target workspace, including the specific worktree. Use that workspace's **calling harness** directory: Hermes uses `<workspace>/.hermes/`, Cursor `.cursor/`, Codex `.codex/`, and Pi `.pi/`. A Hermes task delegated to Cursor therefore keeps its record under `.hermes/`, not under the installed skills directory or the user's global home. Big Bang uses the caller's directory, not a `.big-bang` directory. Reuse the caller-supplied location throughout follow-ups.

Store records under `<harness-dir>/agent-sessions/<worker>/<unique-record>.md`, with evidence or native session files in an adjacent conversation-specific directory when the CLI supports local storage. Choose a filesystem-safe unique record name; do not turn an unvalidated native ID into a path. Keep separate worktrees and remote machines separate. For an SSH worker, record the machine/profile and remote absolute workspace; do not treat identical paths on different machines as the same target. Resolve session files on the recorded host and keep the same explicit machine selector for discovery, resume, and inspection.

Before the first history write, create or append to `<harness-dir>/.gitignore`, preserving existing rules:

```gitignore
/agent-sessions/
```

In a Git workspace, verify the intended record path with `git check-ignore -v -- <workspace-relative-record-path>` and check `git ls-files -- <workspace-relative-harness-dir>/agent-sessions`. Effective exclusion and no tracked history are required before saving. If session files are already tracked, identify the exact files and remove only authorized history from the index while preserving working copies; ignoring does not remove past commits. Never rewrite repository history as part of recording a session. Keep existing tracked harness settings and rules visible to Git; avoid a blanket `*` ignore.

For a non-Git workspace, still create the local `.gitignore`. These metadata writes do not authorize source changes or relax the child's read-only mode. If the workspace forbids even metadata writes, report that persistence is unavailable rather than writing elsewhere without agreement.

Completion: one workspace-local location is selected and new history will stay outside Git commits.

## 2. Choose continuity before dispatch

Read relevant records in the selected store before starting a new conversation. Match task purpose, worker CLI, machine, and resolved workspace; compare the recorded branch/HEAD and current worktree changes. A changed HEAD calls for reviewing the delta, not assuming old findings still hold.

Prefer the same verified live agent for a follow-up. Otherwise resume the **explicit recorded native session ID or file**. Herdr agent names and pane IDs locate live processes; they are not durable native conversation IDs. Verify a live pane still hosts the recorded agent before sending input. Avoid latest-session shortcuts in shared workspaces.

If several records are plausible, use task evidence to select; ask only when ambiguity remains material. If the native session is missing, incompatible, or cannot be recovered, start a new conversation with the relevant summary, decisions, evidence, and next action, and record its predecessor and the recovery reason. Mark this as context reconstruction, not native resumption. An unrelated task starts a separate record.

Reapply the current request's scope and permissions on resume. Historical notes supply context, not new authority. Do not send the whole history when a relevant checkpoint suffices.

Completion: a live conversation, explicit resumable session, or documented reconstruction is selected for this task.

## 3. Record checkpoints

Create the record at dispatch, even if the native ID is initially `pending`. Fill in the ID from actual CLI output, session metadata, or a supported session command as soon as available; use `unavailable` with a reason rather than inventing one. Keep credentials, tokens, secret-bearing prompts, and private keys out of the record.

Keep a current summary followed by timestamped checkpoints. Include:

- Task, acceptance criteria, current authorized scope, calling harness, and record owner.
- Machine, absolute workspace/worktree, branch and HEAD when available.
- Worker CLI/version, provider/model, native session ID/file, and verified resume method.
- Optional live Herdr machine/session, agent name and pane ID; mark stale handles after exit.
- Decisions and useful findings, changed paths, verification commands/results, and retained evidence paths.
- State (`running`, `blocked`, `completed`, `interrupted`, or `failed`), last observed progress, blockers, and next action.

Update after a completed turn, a material decision, a timeout inspection, advice, a blocker, and before handoff, interruption, or pane cleanup. Record a wait timeout as an observation; keep `running` if the worker is still working. On completion, retain the record and native session for future follow-ups; pane cleanup does not delete history.

For long tasks, checkpoint meaningful progress without copying full transcripts. Evidence needed after a temporary worktree is removed must be retained in the calling workspace before cleanup. Recheck Git exclusion before handoff and report the absolute record path with any continuity limitation.

Completion: another orchestrator can identify the session, understand the last verified state, and continue without rediscovering the work.
