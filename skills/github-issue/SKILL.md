---
name: github-issue
description: >-
  GitHub issue: create a Japanese-language issue, or produce a draft for user
  approval without posting.
---

# GitHub issue

Create or draft a GitHub issue whose user-facing title and prose are Japanese.

**Japanese invariant** (check at skill start and again before create/draft handoff): classify every title and user-written prose block as `Japanese` or `exception(reason)`. Allowed exceptions: template-fixed headings, code, identifiers, URLs, verbatim quotes. Unclassified must be zero. Do not rely on character-class heuristics.

Norms: read [`../japanese-tech-writing/SKILL.md`](../japanese-tech-writing/SKILL.md) and apply to prose. Raw logs, command output, and diffs are out of scope. Checklist explanatory text is in scope.

Prefer repository templates for structure. Use the skill default outline only when no usable template exists.

## Branches

Pick exactly one before Step 5:

| Branch | Outcome |
| --- | --- |
| `create` | Post with `gh issue create` after approval |
| `draft-only` | Hand title, body, and target repo to the user; do not post |

## Steps

### 1. Pin repository and check duplicates

Resolve `gh repo view --json nameWithOwner`. Pass `-R <owner/repo>` on every later `gh` call.

Classify as one of: bug / feature request / improvement.

Search with `gh issue list -R <owner/repo> --state all --search '<query>' --limit <N>`.

Completion: kind is fixed; every search query, candidate number/URL, and duplicate judgment is recorded. On duplicate, stop create/draft and propose commenting on the existing issue.

### 2. Classify template kind

Inspect `.github/ISSUE_TEMPLATE/`. Distinguish Markdown templates, YAML issue forms, and `config.yml`.

- Markdown template → keep its headings
- YAML issue form → do not use body-file create; show field mapping or web flow to the user and stop this skill's create path
- `config.yml` only / no template → default outline: Background / Observed / Expected / Repro / Impact / Notes

Completion: chosen template path and kind plus every required field are listed. If a YAML issue form is mandatory, stop without body-file create.

### 3. Gather facts

Inspect code, logs, and command output. Mark anything unverified as `unconfirmed` in the body.

Completion: every heading has facts labeled confirmed or unconfirmed.

### 4. Write the Japanese body

Apply [`../japanese-tech-writing/SKILL.md`](../japanese-tech-writing/SKILL.md) to prose. Re-check the Japanese invariant.

Completion: every required field is non-empty or `N/A(reason)`; no leftover placeholders; Japanese invariant classification has zero unclassified blocks.

### 4b. Draft-only handoff (draft-only branch)

If the user chose draft-only (or asked only for a draft), present title, body, and target repo, then stop.

Completion: title, full body, and `owner/repo` were shown; no `gh issue create` was run.

### 5. Approve and create (create branch only)

Present the draft and repo name; confirm labels and assignees.

```
gh issue create -R <owner/repo> --title <var> --body-file <temp> [--label <...>] [--assignee <...>]
```

Write the temp file as UTF-8 without BOM. Delete it on both success and failure. Do not use shell heredocs on PowerShell.

Completion: exit 0; `gh issue view` title/body/labels/assignees match the approved draft; URL reported; temp file deleted.
