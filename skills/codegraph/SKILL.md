---
name: codegraph
description: Use codegraph before filesystem search for exploration, review, impact, architecture, coverage, or refactor planning.
---

# CodeGraph

Use this skill when the `codegraph` MCP tools are available. Start from the graph: symbols, callers, callees, imports, tests, dependents, communities, and change risk. Read files to verify what the graph names.

If the graph tools are unavailable, stale, missing coverage for the target language, or too coarse for the question, use file search and file reads. Name the graph gap that caused the fallback.

## Core Rule

Before grep, glob, or broad file reads, ask the graph for the smallest useful structural view:

- `semantic_search_nodes` — functions, classes, modules, or concepts by name or keyword.
- `query_graph` — `callers_of`, `callees_of`, `imports_of`, `tests_for`, and dependency links.
- `get_impact_radius` — what a changed node may affect.
- `get_architecture_overview` and `list_communities` — high-level structure before file reads.

Use filesystem search after this pass to verify exact text, inspect unindexed files, or fill a graph gap.

Completion: the answer cites the graph view used, or names the graph gap that justified filesystem search.

## Tool Selection

| Need | Start with |
| --- | --- |
| Review changed code | `detect_changes`, then `get_review_context` |
| Read source snippets for review | `get_review_context` |
| Estimate blast radius | `get_impact_radius` |
| Identify impacted execution paths | `get_affected_flows` |
| Trace callers, callees, imports, tests, or dependencies | `query_graph` |
| Find symbols or concepts | `semantic_search_nodes` |
| Understand major areas of a codebase | `get_architecture_overview`, `list_communities` |
| Plan renames or dead-code cleanup | `refactor_tool` |

## Fallback Guidance

Use grep, glob, and direct reads when:

- The MCP server is not installed or not exposed in the current session.
- The graph has not indexed the relevant files.
- The task depends on comments, docs, configs, generated files, or non-code
  assets that the graph does not model.
- You need exact text, line numbers, formatting, or a final verification pass.

Keep the fallback scoped to the named gap. Read files to verify exact text, line numbers, and formatting after the graph has narrowed the work.

Completion: filesystem search stays inside the stated gap, and any exact text the answer depends on comes from the files.
