---
name: summary
description: Compact the current conversation into a handoff summary so a fresh session, another harness, or a forked agent can continue the work.
argument-hint: "What will the next session be used for?"
disable-model-invocation: true
---

# Summary

Activate only when the user invokes `/summary` or explicitly asks for a handoff summary. Use it when work must travel: a fresh orchestrator session (to drop a long, token-heavy context), another harness (Hermes → Pi/Cursor/Codex/Claude or back), another directory or repo, a colleague, or a forked side task while this session continues. If nothing travels, prefer the harness's native compact instead.

## Write

Write one short Markdown document that lets a fresh agent continue without rereading this conversation. If the user passed arguments, treat them as the next session's focus and tailor the document to it.

Include, in this order:

1. **Goal** — the user's request and acceptance criteria, in one or two sentences.
2. **State** — done, in progress, and not started; current branch/worktree and absolute workspace path.
3. **Decisions** — choices made and their reasons, plus user preferences and constraints that still apply.
4. **Workers** — each live or resumable worker: harness, model, Herdr name/pane, native session ID or file, and its history record path from [harness-sessions](../harness-sessions/SKILL.md).
5. **Evidence** — last verified results (test commands and exit codes, changed paths) as references, not raw output.
6. **Open issues** — blockers, pending user decisions, and risks.
7. **Next steps** — the immediate next actions, first one concrete.
8. **Suggested skills** — skills the next agent should load (for example `big-bang`, `pi`, `cursor`, `harness-sessions`).

Keep it compact: aim for under ~150 lines. Do not duplicate content already captured in other artifacts (specs, plans, ADRs, issues, commits, diffs, harness-sessions records); reference them by absolute path or URL. Do not paste logs, full diffs, or file contents.

Redact secrets and sensitive data: API keys, tokens, passwords, credential paths' contents, and personal information.

## Save

Save to the OS temporary directory (`$TMPDIR`, else `/tmp`; `%TEMP%` on Windows), not the workspace, as `summary-<workspace-name>-<UTC timestamp>.md`. When the summary continues a harness-sessions record, also add its absolute path to that record's next-action entry. Report the absolute path to the user.

Completion: the file exists, reads back correctly, contains no secrets, and a fresh agent could start from **Next steps** using only the file and the referenced artifacts.

## Resume

A new session given a summary reads it first, loads the suggested skills, reacquires live worker state (`herdr agent get`/`read`) instead of trusting recorded status, and continues from **Next steps**. Treat the summary as context, not as verified current state.
