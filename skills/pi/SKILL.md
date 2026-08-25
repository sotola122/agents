---
name: pi
description: >-
  Delegate bounded review, verification, implementation, smoke, or multimodal
  work to the Pi CLI (`pi --print`).
---

# Pi CLI Delegation

Hand one bounded task to Pi as a child agent. Prefer `--print` (process and exit).
Do not start interactive `pi` for delegation.

Prompt bodies: [`prompts/`](prompts/). CLI assembly: [`references/cli.md`](references/cli.md). Multimodal: [`references/multimodal.md`](references/multimodal.md). OS prerequisites: [`references/prerequisites.md`](references/prerequisites.md).

## Steps

### 0. Smoke (only when asked)

When the user asks to smoke-test or confirm Pi auth / model / connectivity — and only then — run this step before (or instead of) a real task. Otherwise skip to step 1.

Read [provider.yaml](provider.yaml) `smoke:` and pick **one** mode:

| Mode | When | Tuple |
| --- | --- | --- |
| `provider_auth` | User asks only for connectivity / auth | `smoke.provider_auth.model` + `smoke.provider_auth.thinking` |
| `planned_tuple` | Smoke gates a real task | Resolved `--provider` / `--model` from step 4, `thinking: smoke.planned_tuple.thinking` |

Assemble flags per [references/cli.md](references/cli.md) with `--no-tools` and inline prompt from [`prompts/smoke.md`](prompts/smoke.md). Report the exact tuple tested. Do not block a planned task on failure of an unrelated model.

Completion: skipped, or stdout is exactly `OK` (trim whitespace) and exit code is 0. On any other outcome for the chosen mode, **stop** — do not run the real task.

### 1. Choose a permission profile

Read [profiles.yaml](profiles.yaml). Pick **exactly one** profile:

| Task | Profile |
| --- | --- |
| Review, design check, static bug hunt | `review` |
| Build, test, lint, reproduce (no source edits intended) | `verify` |
| Implement, fix, refactor (user explicitly asked) | `implement` |
| Judge only supplied text/diff/images | `no-tools` |

Map to CLI flags:

- `tools: [...]` → `--tools` as **one quoted comma-separated string** on PowerShell (e.g. `--tools 'read,grep,find,ls'`); see [references/cli.md](references/cli.md)
- `exclude_tools: [...]` → `--exclude-tools` as **one quoted comma-separated string** on PowerShell; see [references/cli.md](references/cli.md)
- `no_tools: true` → `--no-tools`
- Apply every `defaults:` flag — including **`no_extensions: true` always** (never drop it for plugin/mcp)

`writable: true` means `bash` is allowed — treat the run as shell-writable.

For `review`, also fix `review_kind`: `change-review` | `static-hunt`.

Completion: profile name, tool flags, and (if review) `review_kind` fixed. Do not invent tool lists.

### 2. Choose modalities (multimodal only)

When the task involves images, PDFs, or browser/UI checks — otherwise skip with an empty modality set.

1. Read [modalities.yaml](modalities.yaml) (parent-only; do not pass YAML paths to the child).
2. Pick zero or more: `vision`, `document`, `browser`.
3. For each, fix `backend` (`none`, `bash`, `plugin`, `mcp`).
4. Split inputs:
   - `cli_attachments` — `@` images and deliberate text (diffs, rule files)
   - `task_input_paths` — filesystem paths the child reads (PDFs go here; never `@` a PDF as vision)
5. Create `artifact_dir`: unique empty dir `<temp>/pi/<timestamp>-<rand>/`. Record under `orchestration_artifacts`.
6. **Validate selected backend**:
   - `compatible_profiles` must include the profile from step 1.
   - Effective allowlist = `profile.tools ∪ backend.tool_names − profile.exclude_tools`. Collision → **stop**. Nonempty `requires_tools` with `no-tools` profile → **stop**.
   - Every `requires_tools` entry must appear in the effective allowlist.
   - `plugin`: absolute `extension_path` exists and is readable; `tool_names` nonempty — else **stop**.
   - `mcp`: absolute `adapter_extension_path` and `mcp_config` exist and are readable; `tool_names` nonempty; parse `mcp_config` JSON; each server `argv[0]` must resolve to a **local executable** (`npx` / `npm exec` / bare package names → **stop**). Local argv prevents package-runner auto-fetch only — it is **not** network isolation.
7. **Document fields** (from modalities.yaml backend): serialize `page_counter` / `text_extractor` / `renderer` (bash) or plugin tools, `max_document_pages`, `max_render_pages`, `page_range`, `render_policy` (`never` | `on_empty_or_layout`), `artifact_dir`. Page count: bash → `pdfinfo`; plugin → plugin tool (no Poppler required for plugin). `page_range` from user-approved `in_scope` only — **never auto-shrink**; if limits cannot fit, **stop** or mark incomplete.
8. **Browser preflight** (typed): resolve `target_url`, `server` (`none` or `{owner, argv, cwd}`), `readiness` `{kind, value}`, `timeout_ms`, `teardown_owner`, `browser_channel`, `artifact_dir`, `visual_check`. Unresolved → **stop** or ask. `server.owner: child` requires `bash` in allowlist; `review` + MCP → `owner` must be `parent` or `external`. Parent starts argv and holds the handle when `owner: parent`. Teardown is **unconditional** at end of run.
9. Set `image_input_planned: true` when vision is selected, or `render_policy != never`, or `visual_check: true`. If true, force `--mode json`.
10. **Prerequisite probe** (bash backends): read [`references/prerequisites.md`](references/prerequisites.md). Probe in the Pi bash environment. On miss → **stop**, show OS install section — do not auto-install. Browser probe must use `browser_channel` and exit nonzero on failure (see prerequisites).
11. **Startup probe** (only when plugin/mcp paths are configured): `pi --print --no-extensions -e <abs> [--mcp-config <abs>] --tools <tool_names> ... "list your available tools"`. Confirm `-e` + `--mcp-config` parse together and expected tools register. Unconfigured → skip. Never install.
12. `upgrade_policy: never` — do not silently promote profile.

Canonical append order: `vision` → `document` → `browser`. Dedupe vision when browser/document implies it.

Completion: modality set fixed; paths absolute and existence-checked; MCP argv local; browser preflight resolved; `image_input_planned` decided; prerequisites present or user notified. Do **not** claim backends are fully executable beyond path/argv checks (unless startup probe ran).

### 3. Choose child skills (opt-in)

Default: no explicit child skills.

When the user names a skill the child must follow:

1. Resolve each path to absolute; verify file or directory exists.
2. Record in run plan; pass one `--skill <abs>` per skill.
3. **Keep `--no-skills`** — explicit `--skill` loads alongside discovery block.
4. Skill load does not widen `--tools`; profile allowlist stays authoritative.

Completion: child skill set fixed (zero or more), every path existence-verified.

### 4. Choose effort and load provider settings

Read [provider.yaml](provider.yaml). Pick **one effort** key using each entry's `when:`. Apply `resolution:` field lists exactly — do not invent another precedence. Record effort key, **reason**, `image_input_planned`, and resolved `--provider` / `--model` / `--thinking`.

If `image_input_planned` and the resolved (or user) model is outside `vision_capable_models` → confirm or refuse.

Retry triggers live in step 7, not here.

Completion: effort key, reason, and resolved tuple recorded in run plan.

### 5. Assemble the prompt

Require `prompts/<profile>.md` for every profile. Missing → **stop**.

Before launch for `change-review`: build a **complete change manifest** into `artifact_dir` and attach via `cli_attachments`:

- `baseline` (sha or `HEAD` + dirty)
- tracked: `git diff --binary <baseline>`, `git diff --name-status <baseline>`
- untracked: `git ls-files --others --exclude-standard`; materialize each as `git diff --no-index --binary /dev/null <path>` (or attach the file)
- If any range is omitted → record `omitted_ranges` in the task block; child must not give an unqualified whole-change pass (`narrowly scoped` or incomplete)

Concatenate in order (dependency closure; each item at most once):

1. **Base** — `prompts/<profile>.md`
2. **Shared multimodal** — if any modality selected, inline `references/multimodal.md` once
3. **Modality references** — selected modalities in canonical order
4. **Modality appends** — canonical order
5. **Lens appends** — `tooling-suggest.md` / `adversarial.md` when requested
6. **Task block** — serialize:

```
objective:
in_scope:
out_of_scope:
acceptance_checks:   # numbered; each independently verifiable
allowed_task_side_effects: none | [explicit list]
orchestration_artifacts: [artifact_dir, diffs, worktrees, ...]
stop_conditions:
cli_attachments: [...]
task_input_paths: [...]
review_kind: change-review | static-hunt   # review only
workspace: in_place | worktree            # verify / implement retry
image_formats: [...]                      # when vision/images
# + document / browser backend fields from step 2
```

Write via UTF-8 recipe in [references/cli.md](references/cli.md).

**Post-assembly check:** scan the assembled prompt for **package-relative pointers** only — patterns like bare `references/…`, `prompts/…`, `prerequisites.md`, or unpath-qualified `modalities.yaml` / `provider.yaml` / `profiles.yaml` as instructions to open those skill files. Absolute task paths and deliberate `@` attachments (including `*.yaml` rule files under review) are allowed. Any unresolved package-relative pointer → **stop** and remove it.

Completion: base → multimodal (if any) → refs → appends → lens → task; zero package-relative pointers; all selected values serialized in the task block.

### 6. Run Pi

From repo root (or materialized worktree). Assemble per [references/cli.md](references/cli.md).

**Before launch on PowerShell, every comma-joined flag value is a single quoted argument.**

```
pi --print [--mode json] \
  --provider <resolved> --model <resolved> --thinking <resolved> \
  --no-session --no-extensions --no-skills [--skill <abs> ...] \
  --no-prompt-templates --no-context-files --no-approve \
  <profile tools flag> [--exclude-tools ...] \
  [-e <extension_path>] [-e <adapter_extension_path> --mcp-config <path>] \
  ['@cli_attachments' ...] \
  <prompt via stdin>
```

Keep `--no-extensions` always. Put `-e` **before** `--mcp-config`. Extend `--tools` with backend `tool_names` when plugin/mcp. Use `--mode text` only when no visual audit and `image_input_planned` is false. Optional lever (not default): `--offline` for startup network ops only — see cli.md.

**Workspace materialization** (`verify` when dirty, and `implement` retry attempt 2):

1. **Before attempt 1**, capture an immutable input baseline into `artifact_dir`:
   - `base=$(git rev-parse HEAD)`
   - `git diff --binary HEAD > dirty.patch`
   - untracked via `git ls-files --others --exclude-standard -z`
   - **Archive untracked contents** into `artifact_dir/untracked/` with type/mode/symlink preserved (`cp -a` / equivalent) — do not rely on the live worktree later
2. `git worktree add --detach <dir> $base`
3. If dirty.patch nonempty: `git -C <dir> apply --index --binary`
4. Restore untracked **from the archive** (not from the live tree) with type/mode/symlink preserved
5. Manifest: base sha, dirty.patch hash, each untracked path + hash + type + mode + symlink target; recompute in worktree and compare
6. Submodule/ignored needed, apply failure, or manifest mismatch → destroy worktree, fall back to **in_place**. Never report green from bare `HEAD` while dirty changes exist.
7. Record `workspace` choice and reason in the run plan
8. After the run: copy retained evidence into `artifact_dir`. Then:
   - **`verify`:** `git worktree remove` + `git worktree prune` unconditionally
   - **`implement` retry success:** produce `git -C <dir> diff --binary $base > artifact_dir/result.patch` (include untracked additions), apply/validate into the **destination workspace**, confirm expected paths exist, **then** remove the worktree. If apply to destination fails → `Delegation incomplete` (keep the worktree path in the report; do not claim success).
   - **`implement` retry failure:** remove the worktree; keep attempt output

Completion: Pi exited; stdout captured; JSON event log retained when `--mode json`; failures reported without silent local substitution; successful implement-retry edits delivered to the destination workspace.

### 7. Verify the handoff

**JSON success signal** (when `--mode json`): process exit 0, and the event stream contains `"type":"agent_end"` with `"willRetry":false`, then `"type":"agent_settled"`. Extract final assistant text from the last assistant `message_end` / `turn_end`. Absent this signal → treat as incomplete even if exit 0.

Task completion — all required:

1. Process exit 0 and (if json) the success signal above
2. Profile output heading present (`# Review Result` / `# Verify Result` / `# Implement Result` / `# Judgment Result`)
3. Every `acceptance_checks` item has explicit evidence
4. Task side effects ⊆ `allowed_task_side_effects` (ignore `orchestration_artifacts`)

Any miss → report **`Delegation incomplete`** with unmet item names; do not declare success.

Also:

- **Multimodal:** Vision evidence rules from the materialized multimodal reference (run inputs vs generated outputs). Generated evidence only under this run's `artifact_dir`; require successful image-delivery in the JSON log (not merely a tool call) and recorded capture exit code.
- **Missing modules:** present [`references/prerequisites.md`](references/prerequisites.md) install block to the user; never auto-install.
- **`implement`:** `git status --short`, `git diff --stat`, relevant tests.
- **`verify`:** recapture status and content-level diffs/hashes; report newly dirty and changed-already-dirty paths.
- **Retry** (provider.yaml `retry.max_attempts: 2`): on implement failure matching `implement_alternate.when`, keep attempt-1 output, materialize a **fresh** copy from the pre-attempt-1 baseline, re-resolve model via `resolution`, run attempt 2. Do not retry from an already-modified tree.

Completion: success only when all acceptance checks pass; otherwise incomplete with named gaps.

## Hard rules

- Explicit tool allowlist always (`--tools` or `--no-tools`).
- Modalities validate profile — never silently upgrade.
- `--no-skills` always; add `--skill` only when step 3 opts in.
- `--no-extensions` always; add `-e` only for configured plugin/mcp paths.
- No auto-install during delegation (`install_policy: never` unless user authorized outside this skill).
- Do not co-edit the same working tree with Pi.
- No `git commit`, `git push`, or PR from Pi.
- No secrets in prompts.
- Prefer isolation defaults; pass rule files with `@path` instead of ambient AGENTS.md.
- Extend via `prompts/append/` — do not fork base prompts per lens.
- Never auto-shrink document `page_range` to fit limits.
