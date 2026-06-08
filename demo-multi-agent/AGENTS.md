# AGENTS.md — Strict project rules for AI coding agents

> These rules are **non-negotiable**. They override any default agent behaviour
> and are stricter than user-level guidance. Re-read this file at the start of
> every task in this repo.

## 1. Code comments and docstrings — no changelog noise

Comments and docstrings describe **what the code does today**, not what it
used to do, what was deleted, or why this version replaces a previous one.

**Banned in code, docstrings, and tests:**
- References to past refactors, migrations, or consolidations
  ("9-table cleanup", "4-table consolidation", "post-PR-#20", "the old X",
  "legacy X", "deleted store", "removed in commit", etc.)
- "Replaces the old …" / "This used to live in …" / "After the refactor …"
- Commit-message-style prose embedded in code ("This change rewires …")
- Justifications phrased as historical narrative

**Required style:**
- Describe the current contract, invariants, inputs, and outputs.
- If you need to explain *why*, explain the present technical reason
  ("best-effort because the work_item may not exist yet"), not the
  historical reason ("because PR #20 deleted the old store").
- Keep docstrings tight. One short paragraph for module/function intent,
  then the contract. Prose belongs in the PR description, not the code.

If past context is genuinely necessary, put it in the **PR description**,
the **commit message body**, or a Confluence/Jira link — never in source.

## 2. Commit messages and PRs — no agent attribution lines

**Banned in commit messages and PR bodies:**
- `🌀 Magic applied with [Wibey VS Code Extension]…`
- `🤖 Generated with [Claude Code]…`
- `Co-Authored-By: Claude …`
- Any other "this was written by an AI" footer, emoji, or signature.

**Banned in commit messages and PR bodies:**
- Changelog-style narrative re-stating what the diff already shows.
- Phrases like "This change re-wires …", "PR #20's consolidation …",
  "left two orphaned intents …".

**Required style:**
- Conventional-commit prefix (`chore:`, `fix:`, `refactor:`, `docs:`,
  `feat:`, `test:`) followed by a short imperative subject (≤ 70 chars).
- Body (if needed): a few crisp bullets stating the new behaviour and
  any non-obvious trade-off. No history, no AI attribution.

Example body:
```
- Emit a `hitl` event after `resolve_approval()` succeeds; carries
  decision, decided_by, resume_value, reason in `domain_data`.
- Best-effort: failures are swallowed so the resume cannot 500.
- `_resolve_or_create_thread` layers cache → `work_item.kind_data.slack_thread`
  → fresh `/slack/post`, persisting the ts back via `merge_kind_data`.
- New `work_item_store.find_by_external_ref` is status-agnostic
  (counterpart to `find_pending_approval_by_external_ref`) so Slack
  thread recovery works after the approval is decided.
```

## 3. Canonical schema invariants

- **4 tables only**: `agent_registry`, `session`, `work_item`, `event`.
  Do not propose, hint at, or add a new table. Use the JSONB columns
  (`kind_data`, `domain_data`) for side-channel state.
- Persistence helpers live in `storage/`. `from storage.<x>_store import
  <x>_store` is the only correct import — never reach into `storage/`
  internals from outside that package.
- `event_store.append_event` requires `session_id`, `agent_id`,
  `tenant_id`, `event_type`, `work_item_id`, and `domain_data`.
  Best-effort emits must swallow exceptions and log a warning.

## 4. Tests

- Pin contracts, not implementation. A test that breaks when an
  internal refactor doesn't change behaviour is over-fit.
- Test docstrings follow the same rule as code comments: describe the
  invariant under test, not the history.
- Use `sys.modules["storage.<x>_store"]` to patch the module attribute
  when monkey-patching store singletons — the package `__init__` shadows
  the module attribute with the singleton instance.

## 5. Workflow

- Ask before committing. Ask before pushing. Ask before opening a PR.
- Run the unit-test baseline (`python3 -m pytest tests/unit/ -q`)
  before any commit that touches `agent_factory/`, `storage/`, or
  `tests/`. Report the pass count.
- One in-progress todo at a time.

## 6. `agent_factory/` and `storage/` are golden records — touch with care

`agent_factory/` is the generic substrate every pack rides on.
`storage/` is the canonical persistence layer.  Both are
**pack-agnostic by contract**: pack vocabulary (SNOW, GIF, ModSpace,
INC, sys_id, etc.) must never leak into either package.

### 6.1 Confirmation gate

Any change inside `agent_factory/` or `storage/` — including renames,
docstring edits, log-line wording, and "obvious" cleanups — requires
**explicit user confirmation before the edit**.  State the change,
name the file and symbol, then wait for "go".  Edits confined to
`packs/<pack_id>/`, `tests/`, `docs/`, or top-level glue (`app.py`,
`postman/`, etc.) do not need this gate.

### 6.2 Canonical vocabulary (framework code uses these names only)

| Slot                   | Meaning                                              |
|------------------------|------------------------------------------------------|
| `external_ref`         | human-facing record key (e.g. `"INC52148837"`)       |
| `external_id`          | opaque upstream record id (e.g. SNOW `sys_id`)       |
| `domain_payload`       | raw upstream payload (was `snow_data`)               |
| `work_item_text`       | flattened text for triage (was `incident_text`)      |
| `WorkItemRequest`      | inbound A2A body model                               |
| `requires_external_id` | post-approval action flag                            |

**Banned in `agent_factory/` and `storage/`** (allowed in `packs/`
and in pack-shaped tests only):

- `incident_number`, `incident_text`, `incident_store`, `sys_id`,
  `snow_data`, `inc_link`
- Hard-coded AD group names (`SG-ModSpace-*`, etc.) — drive them from
  `[access_control].groups` in config
- Hard-coded `DIAG-*` tool IDs as defaults — leave the default empty
  (`""`) and let the pack set the ID in `pack.yaml`

The framework has no upstream-system-specific adapter files.  Ticket
operations go through the generic
`agent_factory/integrations/matbot_services.py` client, whose endpoint
paths and reference-field name are read from
`[default.matbot_services]` in `secrets.toml`.  Pack-specific glue
(thin wrappers calling the client) lives under `packs/<pack_id>/`.

### 6.3 The HTTP surface

- `GET  /.well-known/agent-card.json` — A2A discovery card (one
  umbrella `AgentSkill` per loaded pack plus opt-in per-tool skills)
- `POST /a2a` — A2A JSON-RPC 2.0 entry point
  (`message/send`, `message/stream`, `tasks/get`, `tasks/cancel`).
  Pack is selected via `params.message.metadata.agent_id`; the
  registry default is used when absent.
- `POST /webhooks/slack/events` — Slack Events API receiver
- `GET  /api/dashboard/{homepage,summary,sessions,session/{id}}` —
  internal ops dashboard
- `GET  /healthz`, `GET /readyz`, `GET /api/health` — probes
- `GET  /` — landing SPA; `GET /console` — dev A2A console (when
  `MATBOT_ENABLE_CONSOLE` is truthy)

## 7. How packs work

A pack is a self-contained `packs/<pack_id>/` directory that teaches
the generic substrate how to behave for one problem domain.  The
substrate stays generic; the pack supplies all domain knowledge via
YAML, prompts, templates, and a small `state.py`.

### 7.1 Layout

```
packs/<pack_id>/
├── pack.yaml              # top-level config: pre_triage, slack,
│                          # closure_templates, evidence_extraction,
│                          # approval_workflow, etc.
├── tools.yaml             # tool manifest (5 tool types — see § 7.3)
├── sop-ir.json            # SOP intermediate representation
├── state.py               # pack-specific TypedDict extending
│                          # BaseWorkItemState
├── prompts/               # Jinja2 prompts (triage / diagnostic /
│                          # decision / action / closure)
├── templates/             # Jinja2 closure summaries
│                          # (closure_<verdict>.j2)
└── eval_cases.json        # branch-coverage eval suite
```

### 7.2 The `PreTriageConfig` contract

Packs drive the pre-triage gate entirely through config — the
framework node `agent_factory/nodes/pre_triage.py` does not know which
upstream system it is talking to:

- `fetch_tool`             — tool ID that fetches the payload by `external_ref`
- `fetch_param`            — kwarg name the tool expects (default `external_ref`)
- `payload_field_prefix`   — probed alongside bare keys (SNOW uses `incident_`)
- `external_id_keys`       — payload keys, in order, to read the upstream record id from
- `assignment_groups`, `keywords`, `categories`, `routed_groups`,
  `slack_notification_keywords` — gate rules

### 7.3 Tool types

The framework recognises exactly these `type:` values in `tools.yaml`:

- `python_function`   — direct callable (read-only diagnostics, mocks)
- `llm`               — LLM-driven reasoning step
- `decision_matrix`   — first-class rules engine (declarative)
- `threshold_check`   — generic "values vs limits" with UOM conversion
- `servicenow` | `kafka` | `elasticsearch` | `http` — adapter tools

High-risk actions set `risk: high` and `requires_approval: true`; the
runtime gates them through the approval node.

### 7.4 Closure rendering

`closure_node` extracts `fields` from evidence, merges `triage_data`,
and surfaces canonical state slots (`external_ref`, `external_id`,
`session_id`, `tenant_id`) before rendering the pack's
`templates/<closure_template>.j2`.  Pack templates may reference
either the canonical slot names or any field the pack's own triage
step populates.

## 8. Before making any change

Before adding a feature, fixing a bug, or refactoring, walk the
repository enough to understand where the change belongs.  In
particular:

- Decide whether the change is **generic** (belongs in `agent_factory/`
  or `storage/`) or **pack-specific** (belongs in `packs/<pack_id>/`).
  If unsure, ask.
- **Do not leak generic logic into a pack.**  If two packs would need
  the same code, it belongs in the framework, driven by config.
- **Do not leak pack-specific logic into `agent_factory/`.**  Any
  branch keyed on a pack id, a SNOW field name, a specific group name,
  or a specific tool ID is a smell — replace it with a config knob on
  `pack.config` and let the pack populate it.
- Match the surrounding structure: same file naming, same module
  layout, same node/store conventions.  New features should look like
  they were always there.
- If you can't find the right home for the code in five minutes of
  reading, stop and ask before writing.
