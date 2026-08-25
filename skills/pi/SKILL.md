---
name: pi
description: Operate Pi CLI for bounded coding delegation.
---

# Pi CLI

Operate Pi as a child coding agent through Hermes `terminal` and `process` tools. Keep this skill about executable CLI behavior; task content comes from the current user request.

## When to Use

- The user explicitly asks to run or delegate work to Pi
- A bounded coding task needs a separate CLI agent
- Pi authentication, model access, attachments, or output modes need checking

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
  command="pi --print --no-session --no-extensions --no-skills --no-prompt-templates --no-context-files --no-approve <permission flags> '<task>'",
  workdir="/absolute/project/path",
  timeout=300,
)
```

The isolation flags suppress ambient extensions, skills, templates, and context files. Add those resources explicitly only when the user requests them.

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
- `--no-session` — ephemeral one-shot run
- `--continue` / `--resume` / `--session <id>` — resume intentional state

For a long bounded run, use `terminal(background=true, notify_on_complete=true)` and inspect it with `process`. Interactive Pi requires `pty=true`; prefer print mode for delegation.

## Workspace Safety

Capture `git status --short` and content-level diffs/hashes before writable runs. A worktree created from `HEAD` omits dirty tracked and untracked state; materialize and hash-verify that state before testing it elsewhere, or run in place with explicit side-effect monitoring.

Pi must not commit, push, open a PR, or read secrets unless the user separately requests and authorizes that action.

## Verification

After every run:

1. Check the process exit code and required terminal event when using JSON mode.
2. Preserve Pi's actual output; do not replace a failed run with an unannounced local answer.
3. For writable runs, inspect `git status --short`, the content diff, and relevant tests.
4. Report the exact provider/model and any incomplete checks.

Completion: process success, requested evidence, and workspace side effects are all accounted for.

## Pitfalls

- `--no-extensions` still permits explicitly supplied `-e <path>` extensions.
- `--no-skills` still permits explicitly supplied `--skill <path>` entries.
- PowerShell comma-separated tool lists must be one quoted argument.
- `--offline` blocks startup network operations; it does not make the model call offline.
- Pi child shell commands are POSIX bash; Windows requires a compatible bash environment for shell work.