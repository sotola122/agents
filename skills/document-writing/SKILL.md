---
name: document-writing
description: >-
  ADR / repository documentation: place, research, write, and diff Japanese
  in-repo docs (design notes, ADRs, docs/ explainers).
---

# Document writing

Write Japanese repository documentation (design notes, ADRs, explainers under `docs/`).

**Japanese invariant** (check at skill start and again before handoff): classify every title and user-written prose block as `Japanese` or `exception(reason)`. Allowed exceptions: template-fixed headings, code, identifiers, URLs, verbatim quotes. Unclassified must be zero. Do not rely on character-class heuristics.

## Branches

Choose norms by document kind:

| Branch | Targets | Norms to read |
| --- | --- | --- |
| `readable` | Explainers and articles meant to be read as prose | [`../japanese-tech-writing/SKILL.md`](../japanese-tech-writing/SKILL.md) and [`../cognitive-rhythm-writing/SKILL.md`](../cognitive-rhythm-writing/SKILL.md) |
| `record` | ADRs, short design notes, reference docs | [`../japanese-tech-writing/SKILL.md`](../japanese-tech-writing/SKILL.md) only |

Raw logs, command output, and diffs are out of norm scope. Checklist explanatory text is in scope.

Prefer templates or peer documents for structure. Invent an outline from the document role only when none exist.

## Steps

### 1. Fix role and path

Read existing `docs/` layout and naming. For ADRs, follow numbering and peer format. Pick `readable` or `record`.

Completion: path, role, audience, naming rationale, template or peer source, and chosen branch are recorded.

### 2. Align structure

Take heading order from a template or peer doc; otherwise derive from role.

Completion: heading order, every required section, and adoption source are listed.

### 3. Gather facts

Read code, config, and decision history. Do not write unverified claims as fact.

Completion: every section has evidence or an explicit unconfirmed marker.

### 4. Write Japanese prose

Apply the norms for the chosen branch. One sentence per line, paragraph writing, footnotes for digressions. Re-check the Japanese invariant.

Completion: every prose block classified under the Japanese invariant with zero unclassified; no placeholders; formatting rules applied.

### 5. Review

**`readable` branch:** run all six checks — cognitive-rhythm-writing post-write checklist (topic test, leakage test, tension ledger, beat check, boundary check) plus japanese-tech-writing "ban LLM-ish phrasing".

**`record` branch:** do not load cognitive-rhythm-writing. Run only japanese-tech-writing rules that apply to the draft, including at least: one sentence per line, paragraph topic unity, and ban LLM-ish phrasing. Do not require CRW-named checks.

Completion: for every required check, reported detections, dispositions, and re-check results.

### 6. Show the diff

Completion: full diff of the target document whether tracked or untracked; no unintended other-path changes.
