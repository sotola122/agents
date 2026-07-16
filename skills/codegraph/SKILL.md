---
name: codegraph
description: Use when working in a repository that has the codegraph MCP server available, especially for code exploration, code review, impact analysis, architecture questions, test coverage checks, or refactoring planning. Prefer graph tools before grep, glob, or file reads so you start from structural context, then fall back to filesystem search only when the graph cannot answer the question.
---

# CodeGraph

Use this skill when the `codegraph` MCP tools are available in the current
harness. The graph is useful because it gives structural context first:
symbols, callers, callees, imports, tests, dependents, communities, and change
risk. Start there before scanning files.

If the graph tools are unavailable, stale, missing coverage for the target
language, or too coarse for the question, fall back to normal repository tools
such as file search and file reads. Say briefly that you are falling back and
why.

## Core Rule

Before using grep, glob, or broad file reads to explore code, ask the graph for
the smallest useful structural view:

- Use `semantic_search_nodes` to find relevant functions, classes, modules, or
  concepts by name or keyword.
- Use `query_graph` to trace relationships such as `callers_of`, `callees_of`,
  `imports_of`, `tests_for`, and dependency links.
- Use `get_impact_radius` to understand what a changed node may affect.
- Use `get_architecture_overview` and `list_communities` for high-level
  structure before diving into files.

Use filesystem search after this first pass to verify exact text, inspect
unindexed files, or handle graph gaps.

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

Keep the fallback scoped. The goal is not to avoid reading files; it is to avoid
starting with broad scans when structural context can narrow the work first.
