---
name: big-bang
description: "Cursor executes; Astra orchestrates and writes prose."
disable-model-invocation: true
---

# Big Bang

Activate only when the user invokes `/big-bang` or explicitly requests this workflow. `/big-bang <task>` delegates execution to Cursor through Herdr. Keep this division for the task and its follow-ups until the user changes it. With no task, use the current explicit request; ask if none exists. This is a workflow instruction, not a model switch or technical tool restriction; Hermes versions that ignore `disable-model-invocation` may still list the skill.

## 1. Frame

For delegated work, load `herdr`, `cursor`, and [harness-sessions](../harness-sessions/SKILL.md). Herdr and Cursor own CLI syntax, readiness, permissions, and pane safety; harness-sessions owns local history and continuity. Verify Herdr caller context before controlling any pane. Outside Herdr, ask the user to launch Hermes inside it before delegation. Prose-only work stays with Astra and needs no Cursor readiness check or pane.

Astra owns scope, acceptance criteria, dispatch, user decisions, evidence checks, and prose drafting/editing (including documentation, articles, and skills). Cursor owns exploration, research, detailed technical design, code/configuration edits, tests, and repairs. For writing tasks, delegate substantial fact gathering to Cursor when needed, then let Astra read the relevant sources and author the prose. Otherwise limit Astra's repository reads to dispatch context and targeted verification. Delegate to Cursor rather than spawning more Hermes agents.

Resolve the absolute target directory and checkable completion criteria. Capture existing Git status and content-level changes before writes. Select the calling harness's workspace-local history (for Hermes, `<workspace>/.hermes/agent-sessions/cursor/`) and verify its `.gitignore` before recording. Read matching history and choose a live agent, explicit native session, or new conversation. Astra owns this record; Cursor supplies results rather than writing a competing history. Delegate discovery rather than exploring the repository to prepare a detailed plan.

Completion: each work unit has an owner, target, acceptance criteria, and authorized scope. For prose-only work, Astra writes and verifies the artifact directly; use the remaining steps for Cursor work units.

## 2. Dispatch

Check Cursor readiness once per task. Select the model by difficulty, ambiguity, and risk; state the choice and a short reason at dispatch:

- Composer 2.5: clear, bounded implementation, routine tests, mechanical edits, and straightforward discovery.
- Cursor Grok 4.6: ambiguous diagnosis, cross-module reasoning, design tradeoffs, high-risk changes, and code review. Select an available effort level proportionate to the task. Use Grok to resolve a difficult question, then hand a clear implementation to Composer when that saves work; avoid automatic two-model passes.
- Auto Intelligence: mixed or difficult work suited to automatic routing, only when the installed CLI or authoritative Cursor documentation establishes an explicit selectable Intelligence mode. Generic `auto` alone does not establish that mode. Exclude Intelligence when unsupported or unverified; proceed with Composer or Grok.

Resolve actual IDs from the installed CLI. Review uses Grok or verified Auto Intelligence, not Composer. Treat this as a routing policy, not a claim that one model is always more capable. Escalate after evidence of difficulty rather than repeatedly retrying the same approach. Ask only if no allowed suitable model is available; do not substitute third-party models or Auto Balance.

Default to one worker in an owned sibling Herdr pane, preserving cwd and user focus. Parallelize only independent work; one writer owns a target directory. Create workspaces or worktrees only when requested.

Reuse a verified live worker for follow-ups. When a worker must be started, obtain or select its native conversation ID using the `cursor` skill, then start its interactive TUI:

```text
herdr agent start <unique-name> --kind cursor --pane <returned-pane-id> -- --sandbox enabled --workspace <absolute-target> --model <verified-model-id> --resume <explicit-chat-id>
herdr agent prompt <unique-name> '<task>' --wait --timeout 600000
```

Follow the `cursor` skill's permission rules and record the native ID, live Herdr handles, model, and workspace. If a new conversation's ID is only available after startup, omit `--resume` for that initial launch and replace the history's pending ID as soon as observed. Add `--force` only for authorized writable work. Keep Big Bang in the visible interactive TUI: `--print`, `-p`, print-only output flags, and logging pipelines are headless routes. Wait for interactive readiness before prompting. Quote task text and paths as shell arguments. If interactive startup fails, inspect and report the blocker; do not silently switch execution modes.

Give the worker the complete work unit: request, relevant paths and skill references, acceptance criteria, existing user changes, authorization boundaries, and expected evidence. Request a concise result with changed paths, test commands/results, blockers, and conversation ID when available. Delegate discovery through verification together rather than dispatching individual commands.

Completion: Cursor's interactive TUI is running in the returned pane, and Herdr has observed activity after the work unit was submitted.

## 3. Supervise

Use **at least 600000 ms (10 minutes)** for each task-completion wait, including the initial prompt and every continued wait. Increase the budget for expected long work. A settled completion or blocked state may return earlier; ten minutes is a wait budget, not a minimum task duration or a kill deadline. Startup/readiness checks have their own CLI limits.

```text
herdr agent wait <unique-name> --timeout 600000
herdr agent get <unique-name>
herdr agent read <unique-name> --source recent-unwrapped --lines 120
```

If the outer terminal tool has a shorter wait limit, run the Herdr wait in the background and poll that command using the tool's supported process handle. Keep the worker and the logical ten-minute wait alive; a tool yield or connection timeout is not a worker failure. Give progress updates while supervising.

After a timeout, stalled submission, blocked state, or lost connection, inspect state and recent output and compare with the previous checkpoint before choosing:

| Evidence | Action |
| --- | --- |
| Working with progress, or a known long-running operation | Continue waiting on the same agent for at least ten minutes. Quiet output alone does not establish a stall. |
| Repeated failed approach, missing information, or a recoverable misunderstanding | Give focused advice when the agent can accept it. While working, use only a verified non-interrupting steering/queue mechanism, or wait for input readiness. |
| Approval or question UI | Read the actual request and use existing authorization where applicable; ask the user only for a missing decision. |
| Idle/done | Read the completed response and verify acceptance criteria; the badge alone does not prove success. |
| Unknown state or connection failure | Reacquire state and output, confirm delivery and process identity, then decide. Do not infer failure or resubmit from a lost response. |
| Explicit stop request, unrecoverable failure, or harmful/wrong work that cannot be corrected in place | Preserve results and history, explain the reason, then interrupt only the owned worker as warranted. |

Timeout alone never warrants `ctrl+c`, process termination, pane closure, or duplicate submission. Record the observed state, progress, advice, and chosen next action in the session history. If alternate-screen output is missing, follow the `herdr` skill's temporary-file fallback.

Send repairs and follow-ups with `herdr agent prompt` to the same live agent once it is ready. On restart, resume the explicit Cursor conversation ID selected from local history. If native resumption is unavailable, follow the documented summary-based reconstruction path and retain the predecessor record.

If authentication, sandbox, model access, or approval blocks execution, report the exact command, observed error or blocked UI, and exit code/log path when available, then obtain any missing decision. Distinguish an explicit sandbox override failing from ordinary Cursor startup; an AppArmor suggestion is not a confirmed diagnosis. Astra keeps its prose work but must not silently take over blocked Cursor work or weaken permissions. Honor authorization already provided for commit, push, or other scoped actions; obtain authorization only for actions outside that scope.

Completion: Cursor has finished the turn with evidence for every criterion, or a specific blocker requires user input. The interactive process need not exit.

## 4. Verify and close

Check Cursor's completed response, changed-file scope and targeted diff against the baseline, and raw relevant test output/exit status. Do not equate the Herdr command's exit code with Cursor task success; the interactive process stays alive between turns. Read back the exact target after external writes. Ask Cursor to obtain missing evidence or repair failures rather than redoing its investigation. Add a separate Cursor review when requested or warranted by risk, not automatically for trivial changes.

Finish only when every acceptance criterion is verified; otherwise name incomplete checks. Report results, evidence, model, workspace, and blockers concisely in the user's language. Claim token savings only when measured.

Keep the interactive pane available during verification and follow-ups so the user can inspect the visible work. Before handoff or cleanup, checkpoint decisions, results, unfinished work, native session ID, and evidence, and report the absolute history path. After verification and evidence retention, exit the worker cleanly before closing only panes created for this task. Mark its live handles stale while retaining the native session and local history. Preserve pre-existing panes, workspaces, and user changes. Keep retained evidence available by absolute path.
