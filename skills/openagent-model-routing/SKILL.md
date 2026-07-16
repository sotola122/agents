---
name: openagent-model-routing
description: Use when maintaining oh-my-openagent agent and category model routing profiles in the agent-tools catalog.
---
# OpenAgent Model Routing

The routing catalog is opaque runtime configuration, not a provider inventory.
Keep model strings exactly as supplied by the OpenCode runtime and do not
validate provider credentials or model availability here.

## Source of truth

- `catalog/model-profiles/*.toml` stores profiles.
- `[[agent]]` entries map one or more agent IDs to a `primary` model and an
  optional ordered `fallback` list.
- `[[category]]` entries map category IDs to the same routing shape.
- `catalog/opencode/oh-my-openagent.json` is runtime base configuration only;
  it must not contain `agents` or `categories` routing tables.

## Validation

Every profile has a unique non-empty `id` and description. Agent and category
IDs are non-empty and unique within their respective namespace. Every model
object has a non-empty string `model`; `variant`, when present, is a scalar
string or number accepted by the native runtime. Do not infer or rewrite IDs.

## Rendering

Use `render_openagent_config(root, profile)` to load the base JSON, remove any
base `agents` and `categories` keys, and inject the selected profile's routing
objects. The returned object is deterministic and contains no provider catalog
or credential data.

Review the rendered JSON and run the routing-focused tests after changes.
