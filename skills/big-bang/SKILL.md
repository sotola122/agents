---
name: big-bang
description: "Cursor executes; Astra orchestrates and writes prose."
disable-model-invocation: true
---

# Big Bang

Activate only when the user invokes `/big-bang` or explicitly requests this workflow. `/big-bang <task>` delegates execution to Cursor through Herdr. Keep this division for the task and its follow-ups until the user changes it. With no task, use the current explicit request; ask if none exists. This is a workflow instruction, not a model switch or technical tool restriction; Hermes versions that ignore `disable-model-invocation` may still list the skill.

## 1. Frame

For delegated work, load `herdr` and `cursor` with `skill_view`; they own CLI syntax, readiness, permissions, and pane safety. Verify Herdr caller context before controlling any pane. Outside Herdr, ask the user to launch Hermes inside it before delegation. Prose-only work stays with Astra and needs no Cursor readiness check or pane.

Astra owns scope, acceptance criteria, dispatch, user decisions, evidence checks, and prose drafting/editing (including documentation, articles, and skills). Cursor owns exploration, research, detailed technical design, code/configuration edits, tests, and repairs. For writing tasks, delegate substantial fact gathering to Cursor when needed, then let Astra read the relevant sources and author the prose. Otherwise limit Astra's repository reads to dispatch context and targeted verification. Delegate to Cursor rather than spawning more Hermes agents.

Resolve the absolute target directory and checkable completion criteria. Capture existing Git status and content-level changes before writes. Delegate discovery rather than exploring the repository to prepare a detailed plan.

Completion: each work unit has an owner, target, acceptance criteria, and authorized scope. For prose-only work, Astra writes and verifies the artifact directly; use the remaining steps for Cursor work units.

## 2. Dispatch

Check Cursor readiness once per task. Select the model by difficulty, ambiguity, and risk; state the choice and a short reason at dispatch:

- Composer 2.5: clear, bounded implementation, routine tests, mechanical edits, and straightforward discovery.
- Cursor Grok 4.6: ambiguous diagnosis, cross-module reasoning, design tradeoffs, high-risk changes, and code review. Select an available effort level proportionate to the task. Use Grok to resolve a difficult question, then hand a clear implementation to Composer when that saves work; avoid automatic two-model passes.
- Auto Intelligence: mixed or difficult work suited to automatic routing, only when the installed CLI or authoritative Cursor documentation establishes an explicit selectable Intelligence mode. Generic `auto` alone does not establish that mode. Exclude Intelligence when unsupported or unverified; proceed with Composer or Grok.

Resolve actual IDs from the installed CLI. Review uses Grok or verified Auto Intelligence, not Composer. Treat this as a routing policy, not a claim that one model is always more capable. Escalate after evidence of difficulty rather than repeatedly retrying the same approach. Ask only if no allowed suitable model is available; do not substitute third-party models or Auto Balance.

Default to one worker in an owned sibling Herdr pane, preserving cwd and user focus. Parallelize only independent work; one writer owns a target directory. Create workspaces or worktrees only when requested.

Start Cursor's interactive TUI with `herdr agent start <unique-name> --kind cursor --pane <returned-pane-id> -- --sandbox enabled --trust --workspace <absolute-target> --model <verified-model-id>`, following the `cursor` skill's permission rules. Add `--force` only for authorized writable work. Do not use `--print`, `-p`, `--output-format`, `--stream-partial-output`, or a logging pipeline for Big Bang delegation: even stream-JSON in a Herdr pane is headless execution, not the visible agent TUI. Wait for interactive readiness, then submit the complete work unit with `herdr agent prompt <unique-name> '<task>' --wait --timeout 120000`. Quote task text and paths as shell arguments. If interactive startup fails, inspect and report the blocker; do not silently fall back to print mode.

Give the worker the complete work unit: request, relevant paths and skill references, acceptance criteria, existing user changes, authorization boundaries, and expected evidence. Request a concise result with changed paths, test commands/results, blockers, and conversation ID when available. Delegate discovery through verification together rather than dispatching individual commands.

Completion: Cursor's interactive TUI is running in the returned pane, and Herdr has observed activity after the work unit was submitted.

## 3. Supervise

Use bounded `herdr agent prompt --wait` / `herdr agent wait` calls. On timeout, stalled submission, or a blocked state, inspect `herdr agent get` and `herdr agent read --source recent-unwrapped` before waiting again or intervening; do not blindly resubmit. Read concise completion output first. Herdr idle/done means the TUI is ready for input, not that acceptance criteria passed. If alternate-screen output is missing, follow the `herdr` skill's temporary-file fallback.

Send repairs and follow-ups with `herdr agent prompt` to the same live agent. Resume an explicit Cursor conversation ID only when restarting is necessary; avoid implicit latest-conversation selection in a shared workspace.

If authentication, sandbox, model access, or approval blocks execution, report the exact command, observed error or blocked UI, and exit code/log path when available, then ask for the required decision. Distinguish an explicit sandbox override failing from ordinary Cursor startup; an AppArmor suggestion is not a confirmed diagnosis. Astra keeps its prose work but must not silently take over blocked Cursor work or weaken permissions. Commit, push, credential access, and destructive operations require separate user authorization.

Completion: Cursor has finished the turn with evidence for every criterion, or a specific blocker requires user input. The interactive process need not exit.

## 4. Verify and close

Check Cursor's completed response, changed-file scope and targeted diff against the baseline, and raw relevant test output/exit status. Do not equate the Herdr command's exit code with Cursor task success; the interactive process stays alive between turns. Read back the exact target after external writes. Ask Cursor to obtain missing evidence or repair failures rather than redoing its investigation. Add a separate Cursor review when requested or warranted by risk, not automatically for trivial changes.

Finish only when every acceptance criterion is verified; otherwise name incomplete checks. Report results, evidence, model, workspace, and blockers concisely in the user's language. Claim token savings only when measured.

Keep the interactive pane available during verification and follow-ups so the user can inspect the visible work. After verification and evidence retention, exit the worker cleanly before closing only panes created for this task. Preserve pre-existing panes, workspaces, and user changes. Keep retained evidence available by absolute path.
