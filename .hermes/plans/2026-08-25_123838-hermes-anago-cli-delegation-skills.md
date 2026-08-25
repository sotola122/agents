# Anago CLI Delegation Skills Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Hermes 向け skill の配布先を `anago` 名前空間の下へ移し、Pi・Codex・Cursor CLI へ安全に委譲する `pi`・`codex`・`cursor` skill を提供する。

**Architecture:** catalog の harness 別 target 解決を一箇所だけ変更し、Hermes の skill に限って `skills/anago/<skill-name>` を返す。他 harness の配置と agent/context の配置は維持する。既存の `delegate-pi`・`delegate-codex` package はディレクトリ、frontmatter、内部参照を同時に `pi`・`codex` へ改名し、Cursor は公式 `agent` CLI の print mode を使う同型 package として追加する。

**Tech Stack:** Python 3.11 標準ライブラリ、`unittest`、TOML、Markdown/YAML skill packages、Pi CLI、Codex CLI、Cursor Agent CLI (`agent` / `cursor-agent`)

---

## Current context and decisions

- 現在の Hermes harness root は `~/.hermes`、全 skill target は harness を問わず `skills/<catalog-name>` である (`catalog/core.py:1402-1416`, `catalog/core.py:1429-1434`)。
- 旧 Hermes skill の migration 専用機能は追加しない。既存の `~/.hermes/skills/<name>` は、対象 path を列挙・確認してから手動削除し、その後 `anago` 配下へ apply する。catalog の汎用 stale-output 処理は変更しないが、今回の移行手段としては依存しない。
- local skill は `assets.local.toml` の `[skills]` キーから `skills/<name>` を解決するため、rename に合わせて enable key も変更する必要がある (`catalog/core.py:207-258`)。
- 現行 package は `skills/delegate-pi/` と `skills/delegate-codex/`。前者は multimodal/provider/profile/reference を含む 20 files、後者は profile/prompt を含む 6 filesであり、rename 時に package 全体を保持する。
- Cursor 公式 CLI は `agent -p` / `agent --print` を non-interactive 用として提供する。ローカルの `agent --help` でも `--mode plan|ask`、`--force`、`--sandbox enabled|disabled`、`--trust`、`--workspace`、`--worktree`、`--model`、JSON output が確認できた。実装時は公式 docs と実機 `agent --help` の両方を再確認し、skill の command を現在の CLI と一致させる。
- `writing-for-agents` に従い、各 skill は「順序付きの実行 steps」を主階層に置き、CLI flag 一覧や modality 詳細は参照 file に開示する。各 step は検証可能な completion criterion で閉じ、同じ rule を複数 file に重複させない。

## Confirmed decisions

1. Hermes 標準の **`~/.hermes/skills/anago/*`** を採用する。
2. `anago` 階層は local/external を問わず **Hermes harness に apply する全 skill** に適用する。agent/context と他 harness は変更しない。
3. 旧 Hermes skill は migration code を設けず、確認済み path だけを手動削除する。

## Proposed package shape

```text
skills/
├── pi/
│   ├── SKILL.md
│   ├── profiles.yaml
│   ├── provider.yaml
│   ├── modalities.yaml
│   ├── prompts/...
│   └── references/...
├── codex/
│   ├── SKILL.md
│   ├── profiles.yaml
│   └── prompts/...
└── cursor/
    ├── SKILL.md
    ├── profiles.yaml
    └── prompts/
        ├── smoke.md
        ├── review.md
        ├── verify.md
        ├── implement.md
        └── append/adversarial.md
```

Cursor の profile mapping は、実装時の CLI probe で確認したうえで次を基本とする。

```yaml
profiles:
  review:
    mode: ask
    sandbox: enabled
    force: false
    writable: false
  verify:
    mode: default
    sandbox: enabled
    force: true
    writable: true
    workspace: worktree-preferred
  implement:
    mode: default
    sandbox: enabled
    force: true
    writable: true
  smoke:
    mode: ask
    sandbox: enabled
    force: false
    writable: false
```

`--force` は command auto-approval を伴うため review では使わない。verify は書換え可能として扱い、dirty tree では disposable worktree を必須既定にする。implementation はユーザーが明示的に edit を依頼した場合だけ選択する。

---

### Task 1: Record the confirmed destination contract

**Objective:** Hermes path と namespace 適用範囲を確定し、後続 task が同じ acceptance criteria を使うようにする。

**Files:**
- Modify later: `catalog/core.py:1429-1434`
- Test later: `catalog/tests/test_sync.py`
- Modify later: `README.md:20-27`

**Step 1: Use the confirmed contract**

- root: `~/.hermes/skills/anago/*`
- scope: Hermes harness に apply する全 skill
- old layout: migration code を追加せず、承認済み path を手動削除

**Step 2: Record acceptance examples**

期待値を次で固定する。

```text
Hermes + skill demo   -> ~/.hermes/skills/anago/demo/
Cursor + skill demo   -> ~/.cursor/skills/demo/
Hermes + agent demo   -> unsupported（現状維持）
Hermes + context demo -> unsupported（現状維持）
```

**Step 3: Confirm completion**

Completion: root、scope、旧 layout の扱いが一意であり、Task 2 の failing test に migration branch がない。

**Step 4: Commit**

この task は確認のみなので commit しない。

---

### Task 2: Add a failing Hermes namespace regression test

**Objective:** Hermes skill だけが `anago` の一階層下へ配置され、他 harness が変わらないことを test で固定する。旧配置の migration behavior は test・実装しない。

**Files:**
- Modify: `catalog/tests/test_sync.py:115-179`

**Step 1: Write the direct target test**

`SyncCliTests` に次の test を追加する。

```python
def test_hermes_skill_target_is_namespaced_under_anago(self) -> None:
    asset = core.Asset(
        id="fixture/demo",
        source="fixture",
        kind="skill",
        path="skills/demo",
        target="skills/demo",
        harnesses=("cursor", "hermes"),
    )

    self.assertEqual(core._target_for(asset, "hermes"), "skills/anago/demo")
    self.assertEqual(core._target_for(asset, "cursor"), "skills/demo")
```

**Step 2: Write the integration/apply test**

Fixture を sync し、`plan_changes(..., ("skill",), ("hermes",))` と `apply_changes` を実行する test を追加する。次を全て assert する。

```python
applied = self.home / ".hermes" / "skills" / "anago" / "demo"
self.assertTrue((applied / "SKILL.md").is_file())
self.assertFalse((self.home / ".hermes" / "skills" / "demo").exists())
```

旧 `skills/demo` や旧 applied manifest は fixture に作らない。この test の責務は新規 apply の target だけであり、migration cleanup は対象外とする。

**Step 3: Run tests to verify failure**

Run:

```bash
python -m unittest catalog.tests.test_sync.SyncCliTests.test_hermes_skill_target_is_namespaced_under_anago -v
python -m unittest catalog.tests.test_sync.SyncCliTests.test_hermes_skill_apply_uses_anago_namespace -v
```

Expected: FAIL — current target is `skills/demo`, not `skills/anago/demo`.

**Step 4: Commit the red tests**

```bash
git add catalog/tests/test_sync.py
git commit -m "test: define namespaced Hermes skill targets"
```

---

### Task 3: Implement harness-specific Hermes skill targets

**Objective:** Minimal target resolution changeで Hermes skill のみを `anago` namespace へ配置する。

**Files:**
- Modify: `catalog/core.py:1429-1434`

**Step 1: Add the minimal target branch**

既定案の complete implementation は次とする。

```python
def _target_for(asset: Asset, harness: str) -> str:
    catalog_name = PurePosixPath(asset.target).name
    stem = PurePosixPath(catalog_name).stem
    if asset.kind == "skill":
        if harness == "hermes":
            return f"skills/anago/{catalog_name}"
        return f"skills/{catalog_name}"
    if asset.kind == "agent":
        return f"agents/{catalog_name}"
    if harness == "cursor":
        return f"rules/{stem}.mdc"
    if harness in ("opencode", "omp"):
        return f"rules/{catalog_name}"
    if harness == "pi":
        return PI_APPEND_REL
    raise SyncError(f"未対応の kind×harness です: {asset.kind}×{harness}")
```

設定項目は追加しない。namespace `anago` は今回の product contract であり、YAGNI に従って general-purpose namespace option にしない。

**Step 2: Run the focused tests**

Run:

```bash
python -m unittest catalog.tests.test_sync.SyncCliTests.test_hermes_skill_target_is_namespaced_under_anago -v
python -m unittest catalog.tests.test_sync.SyncCliTests.test_hermes_skill_apply_uses_anago_namespace -v
```

Expected: PASS.

**Step 3: Run the catalog suite**

Run:

```bash
python -m unittest discover -s catalog/tests -v
```

Expected: all tests PASS; Cursor/OpenCode/OMP/Pi/Shared target assertions remain unchanged.

**Step 4: Commit**

```bash
git add catalog/core.py
git commit -m "feat: namespace Hermes skills under anago"
```

---

### Task 4: Rename `delegate-pi` package to `pi`

**Objective:** Package directory、frontmatter、内部 identity を `pi` に統一し、Pi delegation behavior は保持する。

**Files:**
- Rename: `skills/delegate-pi/` → `skills/pi/`（全 20 files）
- Modify: `skills/pi/SKILL.md:1-14,67`
- Modify: `skills/pi/profiles.yaml:1`
- Modify: `skills/pi/provider.yaml:1`
- Modify: `skills/pi/modalities.yaml:1`
- Modify: `skills/pi/references/cli.md:1,70`
- Modify: `skills/git-worktree/SKILL.md:13`
- Modify: `assets.local.toml.example:51-58`
- Modify: `README.md:16,120-123,217-225`

**Step 1: Rename the directory**

Run:

```bash
git mv skills/delegate-pi skills/pi
```

Expected: package contents are preserved under `skills/pi/`; no duplicate old directory remains.

**Step 2: Update package identity**

Change frontmatter to `name: pi`, heading to `# Pi CLI Delegation`, and description to a model-facing pointer whose distinct branches are bounded implementation, verification, review, smoke, and multimodal work. Replace package identity text (`delegate-pi`) with `pi` where it names the skill or its orchestration artifact directory; preserve the actual CLI binary `pi` and command syntax unchanged.

Target description shape:

```yaml
name: pi
description: >-
  Delegate bounded review, verification, implementation, smoke, or multimodal
  work to the Pi CLI (`pi --print`).
```

**Step 3: Prune and co-locate instructions**

Apply `writing-for-agents`:

- keep the seven operational steps in `SKILL.md` in execution order;
- keep provider/model literals only in `provider.yaml`;
- keep CLI quoting and flag assembly only in `references/cli.md`;
- retain modality-only branches behind existing reference pointers;
- end every step with its existing explicit completion criterion;
- remove identity-only comments that no longer change behavior rather than duplicating the rename in every file.

**Step 4: Update external references**

Replace enable key `delegate-pi = true` with `pi = true`; update README examples and `skills/git-worktree/SKILL.md` wording to `pi`/`codex` package names.

**Step 5: Verify package links and stale names**

Run:

```bash
python -m catalog validate
python - <<'PY'
from pathlib import Path
root = Path('skills/pi')
text = (root / 'SKILL.md').read_text(encoding='utf-8')
assert text.startswith('---\nname: pi\n')
for path in root.rglob('*'):
    if path.is_file():
        assert 'delegate-pi' not in path.read_text(encoding='utf-8')
assert not Path('skills/delegate-pi').exists()
PY
```

Expected: both commands exit 0.

**Step 6: Commit**

```bash
git add skills/pi skills/git-worktree/SKILL.md assets.local.toml.example README.md
git add -u skills/delegate-pi
git commit -m "refactor: rename Pi delegation skill"
```

---

### Task 5: Rename `delegate-codex` package to `codex`

**Objective:** Package directory、frontmatter、内部 identity を `codex` に統一し、Codex delegation behavior は保持する。

**Files:**
- Rename: `skills/delegate-codex/` → `skills/codex/`（全 6 files）
- Modify: `skills/codex/SKILL.md:1-18,149-152`
- Modify: `skills/codex/profiles.yaml:1`
- Modify: `skills/git-worktree/SKILL.md:13`
- Modify: `assets.local.toml.example:51-58`
- Modify: `README.md:16,120-123,217-225`

**Step 1: Rename the directory**

Run:

```bash
git mv skills/delegate-codex skills/codex
```

Expected: all prompt/profile files remain under `skills/codex/`.

**Step 2: Update package identity and pointer**

Use `name: codex`, heading `# Codex CLI Delegation`, and a model-facing description covering review, verification, implementation, and smoke branches.

```yaml
name: codex
description: >-
  Delegate bounded review, verification, implementation, or smoke checks to
  the Codex CLI (`codex review` / `codex exec`).
```

Update comments and Anago references that name the old package. Preserve the existing explicit sandbox mapping and the `review` custom-prompt/scope-mode distinction.

**Step 3: Apply writing-for-agents pruning**

- keep profile selection and command mapping co-located;
- keep command-specific model flags (`-m` vs `-c model=...`) in one section;
- retain checkable completion criteria;
- avoid copying the full CLI reference into `SKILL.md` when `codex --help` is the environment source of truth.

**Step 4: Update enable/docs references**

Replace `delegate-codex = true` with `codex = true` and ensure README lists `skills/pi`, `skills/codex`, and the new `skills/cursor` as Anago harness skills.

**Step 5: Verify package links and stale names**

Run:

```bash
python -m catalog validate
python - <<'PY'
from pathlib import Path
root = Path('skills/codex')
text = (root / 'SKILL.md').read_text(encoding='utf-8')
assert text.startswith('---\nname: codex\n')
for path in root.rglob('*'):
    if path.is_file():
        assert 'delegate-codex' not in path.read_text(encoding='utf-8')
assert not Path('skills/delegate-codex').exists()
PY
```

Expected: both commands exit 0.

**Step 6: Commit**

```bash
git add skills/codex skills/git-worktree/SKILL.md assets.local.toml.example README.md
git add -u skills/delegate-codex
git commit -m "refactor: rename Codex delegation skill"
```

---

### Task 6: Add the `cursor` CLI delegation package

**Objective:** Cursor Agent CLI に bounded task を委譲し、permission profile、prompt assembly、side-effect verification を明示する skill を追加する。

**Files:**
- Create: `skills/cursor/SKILL.md`
- Create: `skills/cursor/profiles.yaml`
- Create: `skills/cursor/prompts/smoke.md`
- Create: `skills/cursor/prompts/review.md`
- Create: `skills/cursor/prompts/verify.md`
- Create: `skills/cursor/prompts/implement.md`
- Create: `skills/cursor/prompts/append/adversarial.md`
- Modify: `assets.local.toml.example:51-60`
- Modify: `README.md:16,120-124,217-226`

**Step 1: Probe the installed CLI and official docs**

Run:

```bash
agent --version
agent --help
agent status
```

Cross-check `https://cursor.com/docs/cli/headless` and `https://cursor.com/docs/cli/reference/parameters`. Do not run a paid smoke task in this step. Completion: binary name, auth-status command, print flag, mode choices, sandbox choices, force semantics, trust behavior, workspace/worktree flags, and output formats are recorded from current sources.

**Step 2: Write `profiles.yaml`**

Create the profile mapping shown under “Proposed package shape,” adjusted only where the Step 1 probe disproves a flag. Each profile must explicitly declare `writable`; `verify` must say that `--force` makes it shell/file writable even when the prompt requests no edits.

**Step 3: Write the four base prompts**

Use the existing Pi/Codex prompt contracts as the local style reference, not as copy-paste bodies. Each prompt must require one stable output heading and evidence for every acceptance check:

```text
# Review Result
# Verify Result
# Implement Result
```

`smoke.md` must request exactly `OK`. `review.md` must prohibit file modifications. `verify.md` must request command evidence and no intentional source edits while acknowledging technical writability. `implement.md` must prohibit commit/push/PR and require changed-file/test reporting.

**Step 4: Write the adversarial append**

Create `prompts/append/adversarial.md` as a narrow lens applied after the base prompt. It should strengthen hostile/edge-case review without duplicating the review output schema.

**Step 5: Write `SKILL.md` as an executable sequence**

Frontmatter:

```yaml
---
name: cursor
description: >-
  Delegate bounded review, verification, implementation, or smoke checks to
  the Cursor Agent CLI (`agent --print`).
---
```

Required sequence:

1. optional smoke only when asked;
2. choose exactly one permission profile;
3. resolve optional model override;
4. assemble base → append(s) → serialized task block;
5. choose in-place vs disposable worktree before writable runs;
6. run `agent --print` with explicit `--sandbox`, `--trust`, profile mode/force, optional `--model`, and prompt via a temp file/stdin only if the probed CLI supports it; otherwise use a safely constructed argument;
7. verify exit/output contract, acceptance evidence, git side effects, and tests.

Canonical command shapes (subject to Step 1 verification):

```bash
agent --print --mode ask --sandbox enabled --trust "$(<prompt-file)"
agent --print --force --sandbox enabled --trust --workspace <path> "$(<prompt-file)"
```

Do not include `--force` in review/smoke. Do not expose API keys in prompts or command logs. Prefer `--output-format json` only if the observed event schema offers a stable terminal success signal; otherwise capture text plus process exit status.

**Step 6: Add enable/docs entries**

Add `cursor = true` to `[skills]` in `assets.local.toml.example`. Document all three package names and the Hermes destination namespace in README examples.

**Step 7: Verify package structure and commands without delegation**

Run:

```bash
python -m catalog validate
agent --help
python - <<'PY'
from pathlib import Path
root = Path('skills/cursor')
assert (root / 'SKILL.md').read_text(encoding='utf-8').startswith('---\nname: cursor\n')
required = {
    'profiles.yaml',
    'prompts/smoke.md',
    'prompts/review.md',
    'prompts/verify.md',
    'prompts/implement.md',
    'prompts/append/adversarial.md',
}
missing = sorted(path for path in required if not (root / path).is_file())
assert not missing, missing
PY
```

Expected: all commands exit 0; no auth invocation or paid agent run is required for structural verification.

**Step 8: Commit**

```bash
git add skills/cursor assets.local.toml.example README.md
git commit -m "feat: add Cursor CLI delegation skill"
```

---

### Task 7: Add local delegation package regression tests

**Objective:** Future changes cannot silently restore old names or break the three package entrypoints/supporting files。

**Files:**
- Create: `catalog/tests/test_delegation_skills.py`

**Step 1: Write failing/guard tests**

Use stdlib `unittest` only. Resolve repo root from `Path(__file__).resolve().parents[2]`. Add tests that assert:

- `skills/pi/SKILL.md` starts with `---\nname: pi\n`;
- `skills/codex/SKILL.md` starts with `---\nname: codex\n`;
- `skills/cursor/SKILL.md` starts with `---\nname: cursor\n`;
- old directories do not exist;
- every relative Markdown link in each `SKILL.md` that points inside its package resolves to an existing file/directory;
- Cursor required prompt/profile files exist;
- `assets.local.toml.example` has `pi = true`, `codex = true`, `cursor = true` and lacks old enable keys.

Complete test helper:

```python
from __future__ import annotations

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
PACKAGES = ("pi", "codex", "cursor")
LINK_RE = re.compile(r"\[[^]]+\]\((?!https?://|#)([^)]+)\)")


class DelegationSkillTests(unittest.TestCase):
    def test_package_names_match_directories(self) -> None:
        for name in PACKAGES:
            skill = ROOT / "skills" / name / "SKILL.md"
            self.assertTrue(skill.is_file(), name)
            self.assertTrue(
                skill.read_text(encoding="utf-8").startswith(
                    f"---\nname: {name}\n"
                ),
                name,
            )

    def test_package_links_resolve(self) -> None:
        for name in PACKAGES:
            package = ROOT / "skills" / name
            text = (package / "SKILL.md").read_text(encoding="utf-8")
            for relative in LINK_RE.findall(text):
                self.assertTrue((package / relative).exists(), f"{name}: {relative}")

    def test_obsolete_package_directories_are_absent(self) -> None:
        self.assertFalse((ROOT / "skills" / "delegate-pi").exists())
        self.assertFalse((ROOT / "skills" / "delegate-codex").exists())
```

Add the Cursor companion-file and example-config assertions in the same class.

**Step 2: Run the focused test**

Run:

```bash
python -m unittest catalog.tests.test_delegation_skills -v
```

Expected: PASS after Tasks 4-6. To demonstrate the guard, temporarily point one expected companion filename at a nonexistent path, observe one FAIL, then revert that temporary test edit before commit.

**Step 3: Commit**

```bash
git add catalog/tests/test_delegation_skills.py
git commit -m "test: validate CLI delegation skill packages"
```

---

### Task 8: Remove old Hermes skills manually and run end-to-end validation

**Objective:** 旧 Hermes skill を確認済み path だけ手動削除し、code、package、documentation、新規配置 behavior を一つの clean verification pass で確認する。

**Files:**
- Verify only: all changed files
- Machine-local, not committed: `assets.local.toml` only if needed to exercise local packages
- External destination under a temporary `CATALOG_HOME` for the first apply check
- External destination under the real `~/.hermes` only after exact-path approval

**Step 1: Run all tests and validation**

Run:

```bash
python -m catalog validate
python -m unittest discover -s catalog/tests -v
```

Expected: exit 0; all tests PASS.

**Step 2: Exercise apply in an isolated home**

Create a temporary home and a temporary `assets.local.toml` enabling only `pi`, `codex`, and `cursor`; preserve/restore any pre-existing machine-local file in a `try/finally` test script. Run:

```bash
CATALOG_HOME=<temp-home> python -m catalog diff --harness hermes --kind skill
CATALOG_HOME=<temp-home> python -m catalog apply --harness hermes --kind skill
CATALOG_HOME=<temp-home> python -m catalog status
```

Expected:

```text
<temp-home>/.hermes/skills/anago/pi/SKILL.md
<temp-home>/.hermes/skills/anago/codex/SKILL.md
<temp-home>/.hermes/skills/anago/cursor/SKILL.md
```

Assert the three files exist and no corresponding `<temp-home>/.hermes/skills/{pi,codex,cursor}` directories exist. Do not seed old roots or test migration cleanup.

**Step 3: Preview the real old Hermes skill paths**

Read `~/.hermes/.catalog-applied.toml` and select only entries whose `kind` is `skill`, whose root is exactly `skills/<name>`, and whose corresponding path exists under `~/.hermes/skills/`. Exclude `skills/anago`, nested roots, manifest entries outside the old layout, and every directory not owned by the manifest.

Print the deletion candidates one path per line. Completion: every candidate is an exact `~/.hermes/skills/<name>` path and no deletion has occurred.

**Step 4: Delete only the approved old paths manually**

Present the complete Step 3 list for explicit approval. After approval, delete each listed directory individually. Do not use a wildcard against `~/.hermes/skills/`; do not delete `anago/`; do not delete paths absent from the approved list.

Re-run the preview and verify that all approved old paths are absent while every unapproved/user-owned skill remains. This is a one-time operational action: do not add a migration function, compatibility alias, or old-path cleanup branch to `catalog/core.py`.

**Step 5: Apply the namespaced layout to the real Hermes home**

Run only after Step 4 succeeds:

```bash
python -m catalog diff --harness hermes --kind skill
python -m catalog apply --harness hermes --kind skill
python -m catalog status
```

Expected: selected skills exist under `~/.hermes/skills/anago/<name>/`; a second diff is clean.

**Step 6: Inspect scope discipline**

Run:

```bash
git status --short
git diff --stat
git diff --check
git diff -- README.md assets.local.toml.example catalog/core.py catalog/tests skills
```

Expected:

- no files outside the listed scope except this plan;
- no `skills/delegate-pi/` or `skills/delegate-codex/` paths;
- no source lock change (`sources.lock.toml` is unrelated to local assets);
- no migration-specific code or tests;
- no whitespace errors;
- README consistently uses the agreed Hermes path and manual-removal procedure.

**Step 7: Optional real CLI smoke tests**

Only if the user explicitly authorizes provider-backed calls and auth is already configured, run each skill's exact smoke prompt against `pi`, `codex`, and `agent`. Expected: trimmed stdout `OK`, exit 0, and no workspace changes. Otherwise report structural/CLI-help verification as complete and provider connectivity as “not exercised,” never as passed.

**Step 8: Final commit**

If Task commits were created as specified, do not create a redundant aggregate commit. If implementation was intentionally squashed, use:

```bash
git add README.md assets.local.toml.example catalog/core.py catalog/tests skills
git commit -m "feat: add namespaced Anago CLI delegation skills"
```

Completion: full tests pass, isolated apply proves the new layout, approved old Hermes skill paths are manually removed, and the real namespaced apply is verified.

---

## Files likely to change

```text
catalog/core.py
catalog/tests/test_sync.py
catalog/tests/test_delegation_skills.py
README.md
assets.local.toml.example
skills/git-worktree/SKILL.md
skills/delegate-pi/**        -> skills/pi/**
skills/delegate-codex/**     -> skills/codex/**
skills/cursor/**             (new)
```

`sources.toml` and `sources.lock.toml` should not change: these three packages are local assets selected through `assets.local.toml`.

## Validation matrix

| Case | Expected |
| --- | --- |
| Hermes + external skill | `~/.hermes/skills/anago/<name>/` under default scope |
| Hermes + local `pi` | `~/.hermes/skills/anago/pi/` |
| Hermes + local `codex` | `~/.hermes/skills/anago/codex/` |
| Hermes + local `cursor` | `~/.hermes/skills/anago/cursor/` |
| Cursor/OpenCode/OMP/Pi/Shared + skill | Existing `skills/<name>` target unchanged |
| Existing Hermes `skills/<name>` | Preview exact manifest-owned paths; delete approved paths manually before apply |
| Cursor review | read-only mode, sandbox explicit, no `--force` |
| Cursor verify | writable risk explicit; disposable worktree preferred; side effects compared |
| Cursor implement | only after explicit user request; sandbox/force explicit; parent verifies tests/diff |
| Provider smoke not authorized | skipped and reported as untested, not passed |

## Risks and tradeoffs

- **Namespaced scope:** applying `anago` to all Hermes skills intentionally changes external and local skill locations; agent/context and other harnesses stay unchanged.
- **Skill rename compatibility:** callers invoking `delegate-pi`/`delegate-codex` will stop resolving those names. The request explicitly asks for rename, so no alias package is planned; aliases would duplicate context pointers and violate the writing-for-agents single-source rule.
- **Manual old-skill deletion:** destructive and intentionally outside product code. Enumerate manifest-owned paths, obtain approval for the exact list, delete one-by-one, and preserve every unmanaged user directory.
- **Cursor `--force`:** it can approve shell/file operations. Review stays read-only; verify is isolated and treated as writable; implementation requires explicit user intent.
- **CLI drift:** Cursor, Pi, and Codex flags evolve. The skill should cache only orchestration decisions and pitfalls; readily discoverable flag detail remains grounded in each CLI's `--help` output.
- **Paid smoke calls:** command presence/auth status can be checked locally, but an actual model smoke consumes quota and may have external side effects. It remains opt-in.

## Definition of done

- Agreed Hermes destination is implemented and documented exactly.
- Hermes target tests prove namespacing and unchanged non-Hermes targets; no migration-specific code or test is added.
- Skill packages are named exactly `pi`, `codex`, and `cursor`; obsolete package directories and enable keys are absent.
- Every package pointer resolves; Cursor profile/prompt files exist and encode explicit permissions.
- `python -m catalog validate`, focused tests, and full `unittest` discovery pass.
- A temporary-home apply proves the namespaced package paths; approved real old paths are then removed manually before the verified real apply.
- Any provider-backed smoke not explicitly authorized is labeled untested.
