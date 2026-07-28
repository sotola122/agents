---
name: github-pr
description: >-
  pull request: push a commit-ready branch and open a Japanese-language PR.
---

# GitHub PR

Push an already-committed branch and open a pull request. Title and prose are Japanese. Branch creation and committing are out of this skill's scope. Independent of `git-worktree`.

**Japanese invariant** (check at skill start and again before create): classify every title and user-written prose block as `Japanese` or `exception(reason)`. Allowed exceptions: template-fixed headings, code, identifiers, URLs, verbatim quotes. Unclassified must be zero. Do not rely on character-class heuristics.

Norms: read [`../japanese-tech-writing/SKILL.md`](../japanese-tech-writing/SKILL.md) and apply to prose. Raw logs, command output, and diffs are out of scope. Checklist explanatory text is in scope.

Prefer repository templates for structure. Use the skill default outline only when no usable template exists.

## Steps

### 1. Pin repository and base

Parse `gh repo view --json nameWithOwner,defaultBranchRef` via `ConvertFrom-Json` or `--jq '.defaultBranchRef.name'`. Shape: `{"defaultBranchRef":{"name":"main"},"nameWithOwner":"owner/repo"}`. Use a user-specified base when given.

Confirm an attached branch with `git symbolic-ref -q --short HEAD`; stop if detached.

Confirm `git status --porcelain` is empty; stop if the commit-ready precondition fails.

Prefer a fresh compare ref such as `origin/<base>` when fetch works.

Use two-dot `git log <base>..HEAD` for commits reachable only from HEAD, and three-dot `git diff <base>...HEAD` for the merge-base diff.

Completion: repository, fresh base ref, merge-base, HEAD, every commit id, every changed path, and clean status are recorded.

### 2. Load PR template

On the chosen base tree, search in order and stop at the first usable hit:

1. Repository root `PULL_REQUEST_TEMPLATE.md`
2. `docs/PULL_REQUEST_TEMPLATE.md` and `docs/PULL_REQUEST_TEMPLATE/`
3. `.github/PULL_REQUEST_TEMPLATE.md` and `.github/PULL_REQUEST_TEMPLATE/`

If a directory has multiple templates, confirm with the user or record why one matches the change.

If none exist, use the default outline: Summary / Background / Changes / Impact / How to verify / Related issues.

Completion: chosen template path (or default) and every required section are fixed.

### 3. Push

If upstream exists: `git push`. If not: resolve the branch name and run `git push -u <remote> "HEAD:refs/heads/<branch>"`.

Always push when HEAD is ahead of upstream; skipping leaves an stale remote head for the PR.

Force push needs separate approval regardless of default-branch name; cap at `--force-with-lease`.

Completion: push exit 0; upstream set; local HEAD OID equals remote tip OID.

### 4. Write Japanese title and body

Apply [`../japanese-tech-writing/SKILL.md`](../japanese-tech-writing/SKILL.md). Re-check the Japanese invariant.

Use `Closes #N` only when the PR fully resolves the issue; otherwise `Refs #N`.

Completion: Japanese invariant has zero unclassified blocks; every section is non-empty or `N/A(reason)`; issue linkage kind is fixed.

### 5. Approve and create

Present draft plus base / head / draft-vs-ready choice.

```
gh pr create -R <owner/repo> --base <base> --head <branch> --title <var> --body-file <temp> [--draft]
```

Add `--draft` only when chosen. Write temp as UTF-8 without BOM; delete on success and failure. No PowerShell heredocs.

Completion: remote PR base/head/draft/title/body match approval; URL reported; temp file deleted.
