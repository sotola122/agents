---
name: git-worktree
description: User-owned linked worktree create / list / retain / remove.
disable-model-invocation: true
---

# Git worktree

Lifecycle only for user-owned linked worktrees: `list` | `create` | `retain` | `remove`.

Do not perform implementation or verification inside the worktree; return that to the caller.

Disposable worktrees owned by `delegate-pi` or `delegate-codex` are out of scope. Refuse those paths on every entry.

No writing-norm pointers.

## Placement

Default path: sibling `<root>/../<repo>-worktrees/<branch>`.

In-root placement nests a source tree under the source tree. Ignore rules only hide from Git; builds, indexers, and `rg --hidden --no-ignore` still recurse. Use in-root only when the user chooses it, then:

- Ask whether to edit tracked `.gitignore` or `git rev-parse --git-path info/exclude` (prefer local exclude so create alone does not dirty tracked files).
- Verify with `git check-ignore -v -- <path>`.
- Refuse if the current top-level is already inside another worktree (no nesting).

## Canonical create commands

Write the full command for the chosen create kind. Do not describe create as "drop `-b`".

**New branch:**

```
git -C "<root>" worktree add -b "<branch>" "<absPath>" "<startOid>"
```

**Existing branch** (derive and pre-check start OID from the branch tip; do not pass a separate OID arg):

```
git -C "<root>" worktree add "<absPath>" "<branch>"
```

**Detached:**

```
git -C "<root>" worktree add --detach "<absPath>" "<startOid>"
```

Validate branch, path, and start point separately before running.

## Lifecycle (create → later remove)

```
Prepared → Active → Inventory → AwaitApproval → Removing → Removed
```

- AwaitApproval "keep" → Active
- Removing failure → Active (keep the worktree)
- Remove only after the user names the path and explicitly ends it

## Entry: pick one operation

At start, select exactly one: `list` | `create` | `retain` | `remove`. Follow only that section. If the target is delegate-owned, stop immediately.

### list

1. Run `git worktree list --porcelain` from the canonical root.
2. Report path, branch/detached, HEAD OID, and lock state for each user-owned worktree.

Completion: porcelain listing shown; no create or remove ran.

### create

#### 1. Prepare placement

`git rev-parse --show-toplevel` for canonical root; repo name via basename. Default to sibling; for in-root, get exclude approval and `git check-ignore -v`.

Completion: root, path, branch or detached, start OID (or existing-branch tip), unused path, no checkout conflict, and (if in-root) effective ignore are confirmed.

#### 2. Create

Run the matching canonical command.

Completion: `git worktree list --porcelain` shows the exact path, branch/detached, and HEAD OID expected; absolute path reported to the user; work returns to the caller.

### retain

For an existing user-owned worktree the user wants to keep.

1. Confirm the path appears in `git worktree list --porcelain`.
2. Optionally run the Inventory checklist below and report status without removing.

Completion: path confirmed present; user told it is retained; no remove ran.

### remove

For an existing user-owned worktree. Do not run create steps first.

#### 1. Inventory (before any remove approval)

Collect every item, then present them:

- branch vs detached; HEAD OID; local/remote refs containing that OID
- tracked / staged / untracked / ignored files
- recursive submodule status and dirty submodule contents
- upstream presence; if missing, list commits reachable from HEAD not from remotes (`HEAD --not --remotes`). Do not treat a failed `git log @{u}..` as "nothing unpushed"
- `git stash list` (repo-wide; never auto-drop)
- lock state from `git worktree list --porcelain`
- shell cwd moved off the target path

Completion: every item resolved and shown to the user.

#### 2. Explicit end

Name the path and ask to remove or keep. Remove only on explicit end.

Completion: user answer recorded. On keep, stop here (retain).

#### 3. Remove

`git worktree remove <path>` without `--force`. On failure, stay Active and keep the worktree.

Skip `git worktree prune` after a normal remove (unscoped; can touch other worktrees' metadata). If prune is needed, show `prune --dry-run --verbose` and get separate approval.

Branch deletion is a separate confirmation.

Completion: only the named path is gone from `git worktree list` and the filesystem; other worktrees remain; result reported.
