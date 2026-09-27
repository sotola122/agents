---
name: design-docs
description: Create or revise Japanese software, firmware, or hardware design docs for architectural decisions, alternatives, and design review. Use for a design doc or design proposal; produce a 5–10-page document with Mermaid diagrams.
---

# Design docs

Write a reviewable design decision document in Japanese unless the user requests another language. Use [Design Docs at Google](https://www.industrialempathy.com/posts/design-docs-at-google/) as background for decision-focused writing. The user's constraints here take precedence: **target 5–10 pages and never exceed 10 pages**, including diagrams, tables, references, and any appendix. This limit applies to the produced document, not this skill.

## 1. Frame the decision

Identify the reader, the decision they need to make, the target artifact/path, and the known constraints. Read relevant code, specifications, measurements, and prior decisions. Separate verified facts, assumptions, and unresolved questions. Use existing repository document conventions when applicable; use `document-writing` for repository placement and prose conventions, while this skill owns design structure, length, and diagrams.

Resolve what available evidence can answer before asking questions. Ask only about missing information that changes the design; otherwise state the assumption and continue the draft. On revisions, read the current document and preserve still-valid decisions and their rationale.

Completion: scope, decision, evidence, assumptions, and destination are explicit.

## 2. Allocate the document

Adapt the outline to the decision and any required template. A useful starting budget is eight pages; the allocations below include figures and tables rather than reserving extra pages for them.

| Section | Content | Approximate pages |
| --- | --- | --- |
| Context and scope | Objective background and the problem boundary | 1 |
| Goals and non-goals | Success criteria and deliberately excluded adjacent work | 0.5 |
| Proposed design | Structure, key interactions, relevant interfaces and data | 3 |
| Alternatives and decision | Viable options, trade-offs, and selection rationale | 1 |
| Cross-cutting effects | Relevant reliability, performance, security, privacy, operations, cost, or hardware constraints | 1 |
| Delivery and open decisions | Validation, rollout, remaining questions, and sources | 1.5 |

Focus on why the design fits its goals. Link detailed API schemas, code, and measurements instead of duplicating them. Compare realistic alternatives on the same criteria; include retaining the current design when viable. Explain when a rejected option would become preferable. Do not invent alternatives to fill a quota.

Keep the title, date, author, and review status compact on the first page. Use `draft`, `in review`, or `accepted` only when supported by the actual review state. For documents under five pages, check for missing decisions or evidence rather than adding filler; deliver a shorter version only if the user accepts that exception.

Completion: all necessary decisions fit a 5–10-page budget with no extra cover or appendix pages outside the limit.

## 3. Write and diagram

Use concise paragraphs for rationale and tables for exact comparisons. Tie each major choice to a goal, constraint, or evidence. Label uncertain quantities and describe how to verify them. Mention only cross-cutting concerns that affect the design; avoid ceremonial checklists.

Author **all diagrams in Mermaid fenced code blocks**. Choose only the diagrams that explain a relevant relationship:

- `flowchart` for system boundaries, components, dependencies, or processing flow.
- `sequenceDiagram` for message order, update protocols, or interactions.
- `classDiagram` for types, interfaces, ownership, and class relationships.
- `stateDiagram-v2` for lifecycle and transition rules; `erDiagram` for stored relationships.

Use a short title or caption and consistent names shared with the prose. Keep each diagram to one question; split dense diagrams and prefer top-down layouts over wide rows. Include a failure or recovery branch when it affects the decision. UML diagrams remain Mermaid source, not ASCII, PlantUML, or image-generation output. In PDF or Word exports, render that Mermaid source to a legible vector/image and retain the editable source with the document.

Completion: text and diagrams agree on components, interfaces, states, and responsibilities, and the selection rationale is explicit.

## 4. Verify and hand off

Use the repository's existing document renderer when available. Otherwise use the requested format's normal renderer with A4 pages, approximately 11-point body text, and 20 mm margins as the default measuring layout. Render Mermaid diagrams before counting pages; Markdown lines or character counts do not establish a page count.

Inspect the rendered diagrams and pages for syntax errors, cropped labels, unreadable text, and awkward page breaks. Count **all pages** of the resulting document and confirm 5–10. If it exceeds ten, remove repetition and move independent detailed material to linked documents; retain every decision needed to review this design. Keep typography readable rather than shrinking it to meet the limit.

If rendering is unavailable, return a draft with the estimated budget and explicitly mark page count and diagram rendering as unverified. Do not claim the document is ready for review with a verified length until the actual rendering passes.

Check goals against the proposed design, alternatives against the same criteria, and each open question for an owner or a concrete next check. During later implementation, update the affected design decisions and diagrams when evidence changes them. Preserve major prior decisions through version history or a concise linked decision record.

Completion: provide the artifact, verified page count and rendering basis, sources, and remaining decisions. Report any unverified item explicitly; never invent stakeholder approval.
