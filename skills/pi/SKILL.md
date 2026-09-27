---
name: pi
description: Run or resume Pi CLI for delegated coding, inspection, verification, or CLI diagnosis.
---

# Pi CLI

Operate Pi as a child coding agent through Hermes `terminal` and `process` tools. Keep this skill about executable CLI behavior; task content comes from the current user request.

Before ordinary work, load [harness-sessions](../harness-sessions/SKILL.md) to select and protect local history. Use the calling harness directory (for example `.hermes` when Hermes delegates to pi); use workspace-local `.pi` when pi itself is the caller. Keep normal conversations persistent and checkpoint the caller-owned record after each turn or blocker.

## Readiness

Probe the installed binary and selected credentials before a real run:

```text
terminal(command="pi --version")
terminal(command="pi auth check --provider <provider> --model <model> --json")
```

`pi auth check` refreshes expired OAuth credentials unless `--no-refresh` is set. Omit `--credentials`; that option exposes credential material.

Completion: the binary exits successfully and the intended provider/model reports ready.

## Non-Interactive Runs

Use `--print` for bounded work and set `workdir` to the target repository:

```text
terminal(
  command="pi --print --session-dir <absolute-history-dir>/native --no-extensions --no-skills --no-prompt-templates --no-context-files --no-approve <permission flags> '<task>'",
  workdir="/absolute/project/path",
  timeout=300,
)
```

Resolve `<absolute-history-dir>` inside the Git-ignored `agent-sessions/pi/` area before launch. The isolation flags suppress ambient extensions, skills, templates, and context files. Add those resources explicitly when required by the authorized task. Confirm options with the installed `pi --help`; retain session persistence independently of these isolation choices.

### Permission flags

Choose the narrowest tool set that can complete the task:

```text
# Read-only inspection
--tools read,grep,find,ls --exclude-tools bash,edit,write

# Build/test verification; technically writable because bash is available
--tools read,grep,find,ls,bash --exclude-tools edit,write

# User-requested implementation
--tools read,grep,find,ls,edit,write,bash

# Supplied material only
--no-tools
```

`--tools` is a model tool allowlist, not an OS sandbox. Treat every run with `bash`, `edit`, or `write` as writable. One agent owns a writable workspace at a time.

## Provider and Model

Use the configured default unless the user chooses a tuple:

```text
--provider <provider> --model <model> --thinking <off|minimal|low|medium|high|xhigh|max>
```

List candidates with `pi --list-models [search]`. Never print API keys or bearer tokens during routine readiness checks.

## Files and Images

Attach explicit inputs with absolute `@` paths:

```text
pi --print ... @/absolute/path/to/file '<task>'
```

Pi sends supported images as vision input and wraps text files as file content. Preflight every path; a missing attachment exits nonzero. PDFs remain filesystem inputs unless the selected toolchain explicitly extracts or renders them.

## Output and Sessions

- `--mode text` — final text output
- `--mode json` — event stream for machine verification
- `--session-dir <dir>` — place native session files in the selected local store
- `--session <absolute-file-or-exact-id>` — resume the explicitly selected session
- `--no-session` — disposable smoke check or explicit no-history request only

Capture the actual native session file/ID from session output or metadata, verify its workspace, and save it in the caller-owned record. Prefer the explicit absolute session file for a follow-up, retaining `--session-dir`, permission/isolation flags, and the target workdir. Avoid `--continue` or an implicit resume picker when selecting a recorded conversation. Native session contents belong to Pi; append progress only to the separate history record. If the native file is unavailable, use the reconstruction path in harness-sessions.

For long work, use `terminal(background=true, notify_on_complete=true)` and inspect it with `process`. A tool wait timeout calls for state/progress inspection, not automatic termination or duplicate execution. Interactive Pi requires `pty=true`; prefer print mode for delegation.

## Workspace Safety

Capture `git status --short` and content-level diffs/hashes before writable runs. A worktree created from `HEAD` omits dirty tracked and untracked state; materialize and hash-verify that state before testing it elsewhere, or run in place with explicit side-effect monitoring.

Keep commits, pushes, PR creation, and credential access within the user's authorized scope. Reuse existing authorization; ask only when an action extends it.

## Verification

After every run:

1. Check the process exit code and required terminal event when using JSON mode.
2. Preserve Pi's actual output; do not replace a failed run with an unannounced local answer.
3. For writable runs, inspect `git status --short`, the content diff, and relevant tests.
4. Report the exact provider/model and any incomplete checks.

Completion: process success, requested evidence, workspace side effects, and a saved continuity record are all accounted for.

## Pitfalls

- `--no-extensions` still permits explicitly supplied `-e <path>` extensions.
- `--no-skills` still permits explicitly supplied `--skill <path>` entries.
- PowerShell comma-separated tool lists must be one quoted argument.
- `--offline` blocks startup network operations; it does not make the model call offline.
- Pi child shell commands are POSIX bash; Windows requires a compatible bash environment for shell work.
