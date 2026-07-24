---
name: review-synthesis
description: >-
  Anago review synthesis: deduplicate and rank lane findings without inventing new ones. Use after independent lanes finish.
---

# Review synthesis

Invoked by the single Anago `reviewer` agent after lane skills return. This replaces a separate coordinator agent.

## Job

1. Collect findings from completed lanes (and optional harness reviews).
2. Deduplicate by same root cause / same evidence.
3. Rank by severity then confidence.
4. Produce an aggregate report: blockers, high, medium/low, open questions.
5. **Do not invent new findings.** You may only merge, rephrase for clarity, or flag contradictions between lanes.

## Output

- Aggregated finding list with stable IDs when provided
- Explicit `dropped-as-duplicate` notes when merging
- Unresolved disagreements between lanes called out as open questions

## Rules

- Synthesis is not a new review dimension.
- If a lane failed or was skipped, record that in the aggregate status.
