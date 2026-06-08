# Multi-Persona Review & Implementation Plan — 6 Architectural Changes

Target repo: `matbot-multi-agents`
Source request: "Consolidate to 2 HTTP entry points; LLM-driven triage; layered tests;
structured step logs; layered secrets; accept-any-input."
Authority: rules in `AGENTS.md` are non-negotiable; this plan does not violate them.

---

## 0 — Orientation Findings (current state)

| Topic | Current state (verified in repo) |
|---|---|
| HTTP entry points | `/a2a/invoke` (chat), `/a2a/invoke-stream` (chat), `/a2a/work-item/process` (POST), `/a2a/work-item/{external_ref}` (GET), `/a2a/approval/complete`, `/webhooks/slack/events`, `/.well-known/agents.json`, `/api/factory/health`, `/api/factory/tools`, `/api/pack/info`, `/healthz`, `/readyz`, `/dashboard`, `/api/dashboard/{summary,sessions,session/{id}}` |
| Chat endpoints | Exist but bound to `ChatRequest{query: str, ...}` → `langchain_chat.run_chat()`. They do NOT drive the LangGraph work-item pipeline. |
| Work-item runner | `agent_factory/api/work_item_runner.py` → `WorkItemRequest{external_ref, session_id?, domain_payload?}` → compiled LangGraph via `runtime_holder.get_graph(pack_id)`. |
| Triage | 100% deterministic. `pre_triage_node` = pack-config rule gate. `triage_node` = regex extraction. **Only `evidence_node` calls the LLM.** |
| LLM client | `agent_factory/runtime/model_client.py::build_langchain_model_client()` + `llm/azure_handler.py`. Fresh client per call (SOA signature TTL). |
| Logging | `agent_factory/common/logging.py` — contextvars, JSON formatter, `log_operation_timing()`, `log_user_query()`. **No `log_step()` helper.** Graph wrapper catches exceptions into `state.errors`. |
| Secrets | `agent_factory/infrastructure/secrets.toml` — flat `[default.<section>]` (e.g. `[default.azure_chat]`, `[default.postgresql]`, `[default.matbot_services]`, `[default.servicenow_proxy]`, `[default.gif_api]`, `[default.iqs_api]`, …). No `[common.*]` / `[packs.<pack_id>]` split. |
| Tests | `tests/unit/` is flat. Pack tests (`test_gif_tote_nodes.py`, `test_devops_health_pack.py`) live there, not under `packs/<pack_id>/tests/`. `tests/unit/agent_factory/` does not exist. |
| Schema | 4 canonical tables — `agent_registry`, `session`, `work_item`, `event`. No add. |
| Pre-triage config | `PreTriageConfig` exists with `enabled`, `fetch_tool`, `fetch_param`, `payload_field_prefix`, `external_id_keys`, `assignment_groups`, `keywords`, `categories`, `routed_groups`, `slack_notification_keywords`. |

---

## 1 — Multi-Persona Review

### Persona A — Senior Architect
- The chat endpoints (`/a2a/invoke*`) and the work-item endpoint (`/a2a/work-item/process`) currently serve **different pipelines** (chat = retrieval LLM; work-item = LangGraph topology). Collapsing them into a single endpoint means `/a2a/invoke` must become a **dispatcher** that decides *intent* (chat vs work-item vs approval-callback) and routes downstream. That is feasible because LangGraph's `pre_triage`/`triage` already own the "is this in scope" gate — but the routing layer must be added in front of the graph.
- The approval callback (`/a2a/approval/complete`) is **not** a "new run" — it resumes an existing graph by `work_item_id`. Forcing it through `/a2a/invoke` requires an envelope discriminator (`"kind": "approval_callback" | "work_item" | "chat"`) or a metadata convention. Without that, the dispatcher cannot disambiguate.
- The proposed sequence `5 → 6 → 2 → 4 → 1 → 3` is correct: secrets first, then input normalisation, then LLM triage, then logging plumbing, then routes last (because routes depend on all of the above), then tests.
- The plan respects "agent_factory/ is pack-agnostic" — the triage prompt lives at `agent_factory/nodes/prompts/triage_base.j2`, with pack override capability. Good.

### Persona B — Security Engineer
- **Secret layering is the right move**: today every developer reading `secrets.toml` sees all pack credentials. A `[common.*]` / `[packs.<pack_id>]` split lets a future change scope a pack's secrets to its own runtime context only. But the current implementation already commits real secrets (sandbox JWT, postgres password, concord token) to the on-disk file — this plan does NOT exfiltrate; it just reorganises. **Still, every persona should note: `secrets.toml` has hard-coded credentials checked into the repo path; that's a pre-existing exposure, not introduced by this plan.**
- The proposed `get_pack_secrets(pack_id)` helper is fine, but it MUST refuse to fall back to `[common.*]` when a key is missing — otherwise a pack could accidentally read framework secrets. Recommend strict-section semantics with explicit override semantics.
- LLM-driven triage means raw user input is now sent to the LLM gateway. If `input` is a free-form Slack message or JSON blob, callers may include PII. Today's deterministic regex triage never leaves the process. The plan must add an explicit note: **callers must not place PII into `input` unless their pack's LLM endpoint is approved for that data class**. This is a control documented in `secrets.toml.template` comments at minimum.
- The approval-callback's external_ref + work_item_id is the auth boundary. If we route approvals through a generic `/a2a/invoke`, we must not loosen the auth check on which body shapes can resume which work_item.

### Persona C — SRE / Observability
- The structured-log helper (`log_step`) is overdue. Today the graph wrapper logs errors but doesn't emit consistent start/complete pairs with `duration_ms`. The proposed shape (`timestamp, node, session_id, agent_id, work_item_id, status, duration_ms, pack_id`) matches OpenObserve's existing index keys.
- Logging "from inside every node" creates a coupling: every pack-specific node implementation would need to call `log_step`. Better: wrap it once in `GraphBuilder._wrap()` so EVERY registered node automatically emits start/complete/failed lines. This keeps packs from forgetting to log and respects "no pack vocabulary in framework."
- Risk: `log_step()` is INFO on success, so an event-heavy graph (8 nodes × N invocations/sec) will multiply log volume by ~8×. We must verify OpenObserve quota + SIEM ingestion budget.
- The "traceback_id (uuid)" on failure is excellent — pair it with `error.traceback_id` on the persisted `event_store` row for cross-reference.

### Persona D — QA / Test Lead
- Splitting tests into Layer A (`tests/unit/agent_factory/`) vs Layer B (`packs/<pack_id>/tests/`) is **the correct shape** but breaks the current `pytest.ini` discovery if it uses `testpaths = tests/unit`. Need to extend test discovery to include `packs/**/tests/` and `tests/unit/agent_factory/`.
- Existing tests already cover `WorkItemRequest`, idempotency, status endpoint, runner budget, approval route. Most of those will become **near-rewrites** when the route changes to `/a2a/invoke` — the test files themselves can stay, but the request/response contracts will diverge. Plan must allocate time for that.
- Layer-B claim "tests for every Python method in the pack's custom .py files" is ambitious. The existing pack files are: `gif_tote_validation/{ticket_tools.py,email_sender.py,isam_mock.py}` and `devops_health_check/health_checks.py`. That's roughly 8–12 functions total — achievable. But the rule "tests must be self-contained (mock external HTTP/DB calls)" requires httpx mock fixtures the project doesn't have today.
- Triage-LLM tests will be flaky unless the LLM call is deterministically mockable. Recommend wrapping LLM invocation through a thin `agent_factory/nodes/triage_llm.py` adapter that is one easy patch point.
- Decision-LLM-parse-failure test: spec says "no 500, logs warning." The fail-closed behavior (do we fall back to rule-based triage? or skip? or proceed with low confidence?) MUST be defined before we write the test.

### Persona E — Backend / Implementation Engineer
- The work-item endpoint currently does heavyweight orchestration (idempotency truth-table peek, work_item row creation, race-or-detach, finaliser). Replacing the *public* route name with `/a2a/invoke` doesn't get rid of any of that machinery — it just renames the door. Confirm with the user whether the **machinery** is also being collapsed (which would be a much bigger change), or only the **route surface**.
- The plan says: "`/webhooks/slack/events`, `/api/factory/*`, `/api/pack/*`, `/api/dashboard/*` may remain for internal ops/observability." That's a safe carve-out — those routes are observability/dashboards, not external A2A contracts.
- The work-item runner already accepts `domain_payload: Optional[dict]`. The "accept any input" change (Change 6) is mostly a SHAPE change — turning `(external_ref required, domain_payload optional)` into `(input required, external_ref derived)`. The flattening helper is straightforward.
- The LLM triage refactor (Change 2) is the highest-risk one. Today's deterministic triage is pack-agnostic, fast, and free. Replacing it with LLM-driven intent extraction means **every request now costs LLM tokens** (Walmart gateway billing) and **adds 300–2000ms latency**. The 3-minute response budget is large, but if pre-triage rejects a request, today that costs 0 LLM calls; LLM triage would still spend ~1 call for an out-of-scope ticket. Recommend the spec stipulate that the LLM triage runs ONLY after pre-triage passes — and that's already the spec's intent ("Pre-triage (pack selection) still uses the rule-based config from pack.yaml … only the deep triage step becomes LLM-driven"). Confirm.
- `secrets.toml` rename: Dynaconf supports nested sections natively. `config.common.llm.endpoint` works as well as today's `config.azure_chat.LIGHTRAG_AZURE_ENDPOINT`. But every reference site (currently `config.azure_chat.*`, `config.postgresql.*`, etc., scattered across `llm/azure_handler.py`, `agent_factory/runtime/model_client.py`, `storage/*`, `agent_factory/integrations/*`) will need an update. Likely **20–40 reference sites**.

### Persona F — Platform / Product
- The "2 entry points" goal aligns with the broader A2A direction (one verb-shaped contract). Today's surface is confusing: external callers wonder whether to use `/a2a/work-item/process` or `/a2a/invoke`. Consolidating is a win.
- BUT existing production callers (cron poller @ `[default.cron_poller]` configured for `/a2a/work-item/process`; Concord webhook caller; any SNOW-side integration) will need migration. This is a **breaking external contract change**. The plan must include a deprecation period or a redirect during cut-over, OR the user must accept a hard cut and coordinate with callers.
- The "/webhooks/slack/events stays" decision is good — Slack has its own callback URL configured at the Slack app side. Forcing a change there would require admin coordination outside this codebase.

---

## 2 — Change-by-Change: WHAT EXISTS vs WHAT TO BUILD

### Change 5 — Two-file secrets layering (FIRST, per sequence) — REVISED PER USER

**Exists today**
- Single canonical file: `agent_factory/infrastructure/secrets.toml`.
- Akeyless-synced via `run_dev.sh` from `/Prod/WCNP/homeoffice/MATBOT_developers/agent-factory/config`.
  - Sync preserves "local-only sections" verbatim — the merge identifies sections present in the remote payload as authoritative and keeps everything else.
- Flat `[default.<section>]` structure:
  - **Framework-owned (Akeyless authoritative):** `[default.azure_chat]`, `[default.postgresql]`, `[default.matbot_services]`, `[default.work_item_runtime]`, `[default.concord]`.
  - **Local-only / pack-flavoured (preserved during sync):** `[default.cron_poller]`, `[default.servicenow_proxy]`, `[default.slack]` (gif's SSOT channel id), `[default.gif_api]`, `[default.iqs_api]`, `[default.uber_api]`, `[default.uber_keys]`, `[default.isam_api]`.
- `settings.py::get_config()` returns a Dynaconf object with `_DEFAULTS` overlay.

**To build (revised approach)**
- **Keep `agent_factory/infrastructure/secrets.toml` as the framework/common file.** Do NOT restructure to `[common.*]`. Do NOT change the flat `[default.<section>]` shape. Akeyless and `run_dev.sh` continue to own this file unmodified.
- **Move pack-flavoured sections out of the root file into per-pack `secrets.toml`:**
  - New file `packs/gif_tote_validation/secrets.toml` containing the sections that belong to this pack today: `[default.servicenow_proxy]`, `[default.gif_api]`, `[default.iqs_api]`, `[default.uber_api]`, `[default.uber_keys]`, `[default.isam_api]`, and the pack-scoped `[default.slack]` (SSOT channel id).
  - New file `packs/devops_health_check/secrets.toml` (initially minimal — whatever the pack consumes today).
  - Both files follow the **exact same flat TOML shape** as the root file (so pack authors copy the existing pattern).
- **Pack-load-time merge:** when `pack_registry` loads a pack, also load the pack's local `secrets.toml` (when present) and merge it into the active Dynaconf config so pack code can read `config.gif_api.GIF_API_URL` exactly as it does today.
  - Implementation: add a `load_settings_file(...)` call (Dynaconf supports merging additional files at runtime) inside `agent_factory/pack_loader.py` or `registry.py` when a pack is activated.
  - Last-write-wins is acceptable — pack secrets can override framework defaults for that pack's session if they need to, but the standard case is pack adds new sections, not overrides.
- `secrets.toml.template` updated to mirror the new shape (split into "Common (framework)" and "Per-pack (in `packs/<pack_id>/secrets.toml`)").
- `run_dev.sh` Akeyless sync: NO change required. The sync rule "preserve local-only sections" continues to work, but once pack sections are moved into the pack folders, those sections simply won't appear in the root file anymore — so the "preserved" list shrinks (or goes to zero, which is the goal).
- `.gitignore` confirm `packs/*/secrets.toml` is ignored (mirror the existing root `secrets.toml` rule).

**Impact / Shortcomings**
- Touches `agent_factory/pack_loader.py` (or `registry.py`) and `agent_factory/infrastructure/secrets.toml` (framework — confirm-gate).
- Touches `agent_factory/infrastructure/secrets.toml.template` (framework — confirm-gate).
- Touches `packs/gif_tote_validation/secrets.toml` (new file, pack scope — no gate).
- Touches `packs/devops_health_check/secrets.toml` (new file, pack scope — no gate).
- May touch `.gitignore` (root — no gate).
- Existing reference sites (`config.gif_api.*`, `config.iqs_api.*`, …) DO NOT NEED CHANGES — same key paths, just loaded from a different file. This is the big win of this approach vs. the original `[common.*]` restructure.
- The framework reference sites (`config.azure_chat.*`, `config.postgresql.*`, `config.matbot_services.*`) also remain unchanged.
- Backward-compat: a developer with the old all-in-one local `secrets.toml` will have duplicate sections after the move. The cleanest path is: (a) make the move + commit; (b) next Akeyless sync run wipes pack-flavoured sections out of root because they're not in the remote payload (the existing merge already handles this — sections not in remote and not on the "preserved" allowlist drop out). Confirm sync semantics before relying on this.

**Decisions captured**
- User: keep flat `[default.<section>]` structure in both files. No `[common.*]` / `[packs.<pack_id>]` reshape.
- User: 2 files per agent — root (common, Akeyless-managed) + pack-local (domain-specific).
- User: same TOML pattern across both.
- User: pack secrets merged into Dynaconf at pack load.

### Change 6 — Accept any input + route to triage (second per sequence)

**Exists today**
- `WorkItemRequest{external_ref: str, session_id?, domain_payload?: dict}`.
- `triage._build_work_item_text_from_payload()` already flattens a SNOW-shaped dict to text — it's a partial precursor.
- `pre_triage_node` reads `state["domain_payload"]` directly.

**To build**
- New top-level request model `InvokeRequest{input: Any, session_id?, agent_id?, metadata?: dict}` in `agent_factory/api/schemas/request.py`.
- `flatten_input(raw) -> str` in `agent_factory/nodes/pre_triage.py`:
  - `str` → identity
  - `dict` → recursive `key: value` lines
  - `list` → joined lines
  - other → `str(raw)`
- `pre_triage_node` normalises the inbound state:
  - `external_ref`: probe `input.external_ref`, `input.incident_number`, `pt.external_id_keys`, else `None`
  - `work_item_text`: `flatten_input(input)`
  - `domain_payload`: `input` stored as-is (when `input` is a dict)
- If `external_ref is None` after normalisation, decide policy:
  - **Recommend**: generate a synthetic `external_ref` (e.g. UUID) and persist it in `kind_data.synthetic_ref=true`. This way idempotency still works.
- Unit tests for `flatten_input`: str / dict / nested dict / list / int.

**Impact / Shortcomings**
- Touches `agent_factory/api/schemas/request.py` (framework — confirm) and `agent_factory/nodes/pre_triage.py` (framework — confirm).
- Today's idempotency truth-table is keyed on `(pack_id, external_ref)`. If `input` doesn't carry an `external_ref`, idempotency stops working — synthetic ref proposal above mitigates but doesn't eliminate.
- Test impact: `test_work_item_runner_budget.py`, `test_work_item_idempotency_truth.py`, `test_work_item_status_endpoint.py` all assume a structured `WorkItemRequest`. They'll need adapters.

### Change 2 — LLM-driven triage (third per sequence)

**Exists today**
- `triage_node` is regex-only (`_extract_field`, `_extract_multiline_field`, `_extract_external_ref`).
- `evidence_node` already calls the LLM (the only node that does).
- Pack prompts exist at `packs/<pack_id>/prompts/triage.j2` (currently UNUSED — packs ship them but the deterministic triage doesn't consume them).
- LLM client factory at `agent_factory/runtime/model_client.py::build_langchain_model_client()` is reusable.

**To build**
- `agent_factory/nodes/prompts/triage_base.j2` — generic base prompt with `{sop_ir}`, `{raw_input}`, `{instruction}` placeholders. Returns instruction format requiring JSON with `{intent, sop_step, evidence_fields, confidence}`.
- `TriageResult` Pydantic model in `agent_factory/nodes/triage.py`:
  ```
  intent: str
  sop_step: Optional[str]
  evidence_fields: dict[str, Any]
  confidence: float        # 0..1
  raw_response: str
  ```
- `triage_node` (the existing one) keeps producing `triage_data` for back-compat, plus adds `triage_result: TriageResult`.
- Adapter `agent_factory/nodes/triage_llm.py::run_llm_triage(state, pack) -> TriageResult`:
  - Loads pack's `sop-ir.json`
  - Reads `packs/<pack_id>/prompts/triage.j2` if present, else `agent_factory/nodes/prompts/triage_base.j2`
  - Renders + calls `build_langchain_model_client()`
  - Parses JSON; on parse failure returns `TriageResult(intent="unknown", confidence=0.0, ...)` and logs warning (NOT 500)
- Wire `triage_node` to call `run_llm_triage` AFTER the existing regex pass (so existing fields remain populated).

**Impact / Shortcomings**
- Touches `agent_factory/nodes/triage.py`, new `agent_factory/nodes/triage_llm.py`, new `agent_factory/nodes/prompts/triage_base.j2` — all framework files (confirm-gate).
- Token cost on every passed request. Pre-triage gate still rejects out-of-scope without LLM.
- Latency: +300ms–2000ms per request. Mitigate by streaming or by short prompts.
- The pack-override path (pack's `prompts/triage.j2` wins over `triage_base.j2`) means pack authors who already ship a triage prompt (gif_tote_validation does) will need that prompt re-shaped to emit the agreed JSON schema. Document this; pack tests will catch divergence.
- Behaviour on LLM failure: spec says "no 500, logs warning." Confirm with user whether downstream nodes can run on a low-confidence `TriageResult` or whether the pipeline should skip to closure with "triage_failed".

### Change 4 — Structured step-by-step logging (fourth per sequence)

**Exists today**
- `agent_factory/common/logging.py` — JSON formatter, contextvars (`session_id`, `user_id`, `trace_id`), `log_operation_timing()`, `log_user_query()`.
- `GraphBuilder._wrap()` (in `agent_factory/graph/builder.py`) catches exceptions but doesn't emit start/complete/failed log lines.
- Each node does ad-hoc INFO logs (e.g. `logger.info(f"[PRE-TRIAGE] PASS {external_ref}")`) — not structured.

**To build**
- New helper in `agent_factory/common/logging.py`:
  ```python
  def log_step(logger, node_name, *, session_id, agent_id, work_item_id,
               pack_id, status, duration_ms, extra=None,
               error_type=None, error_message=None, traceback_id=None) -> None
  ```
  Emits one INFO (or ERROR) JSON line carrying all the required fields plus optional extras.
- Modify `GraphBuilder._wrap()` (framework — confirm) so EVERY registered node emits:
  - `log_step(..., status="started", duration_ms=0)` before invoking the node
  - `log_step(..., status="completed", duration_ms=N)` after a clean return
  - `log_step(..., status="failed", duration_ms=N, error_type, error_message, traceback_id=uuid())` on Exception
- Node-specific extras stay opt-in via the `extra` dict (e.g. `{"triage_confidence": 0.78}`) — packs can also call `log_step` directly from their custom nodes.
- Add the framework-managed `pack_id` and `work_item_id` to a contextvar (so `log_step` can pick them up without each node passing them).

**Impact / Shortcomings**
- Doing it in `GraphBuilder._wrap()` means we get coverage for every node automatically — including pack-supplied custom nodes — without per-node opt-in. Cleaner than the spec's "Add log_step calls to: pre_triage, triage, evidence, decision, action, approval_gate, closure."
- ~8× INFO log volume — needs OpenObserve quota review.
- "traceback_id (uuid)" cross-reference with `event_store` rows — implementation should also write the same uuid to the failure event's `domain_data` so SIEM searches link cleanly.

### Change 1 — Consolidate to 2 HTTP entry points (fifth per sequence)

**Exists today**
- `/a2a/invoke` and `/a2a/invoke-stream` on `routes/chat.py` — bound to chat (retrieval LLM via `langchain_chat.run_chat`).
- `/a2a/work-item/process` (POST) and `/a2a/work-item/{external_ref}` (GET) on `routes/work_item.py`.
- `/a2a/approval/complete` on `routes/approval.py`.

**To build**
- New `InvokeRequest` (see Change 6). Body: `{"input": any, "session_id"?: str, "agent_id"?: str, "metadata"?: dict, "kind"?: "work_item"|"approval_callback"|"chat"}`.
- Rebuild `routes/chat.py::invoke` and `invoke_stream` as a **dispatcher**:
  - If `kind == "approval_callback"` (or `metadata.approval_work_item_id` is present): route to `dispatch_approval(...)` (in-process, the existing approval-runner).
  - If `kind in ("work_item", None)`: route to the work-item pipeline (atomic claim via `work_item_store.start_work_item_run`, race-or-detach via `finalise_run`, return inline body or 202).
  - If `kind == "chat"`: route to `langchain_chat.run_chat()`.
  - All branches use the SAME response envelope (status, session_id, work_item_id, response, time_taken).
- **Remove** the public route `/a2a/work-item/process` and `/a2a/approval/complete` from `app.py`.
- **Keep**: `/a2a/work-item/{external_ref}` for GET-status polling (the user request says "remove POST routes" but does not say to remove GET; clarify with user — recommendation: keep GET because the dispatcher doesn't have a clean way to GET a status).
- Background processing remains identical — anchor tasks in `app.state.in_flight`, finalise via `finalise_run`.

**Impact / Shortcomings**
- **Breaking external contract**. Every external caller (cron poller, Concord callback, SNOW webhook bridge) must migrate to `/a2a/invoke` with the new body shape. Plan must explicitly note: coordinate cutover with the cron poller config (`[default.cron_poller].AGENT_BASE_URL`) and Concord's configured callback URL.
- The single-endpoint dispatcher carries every request shape — chat and work-item have very different latency profiles (chat ≈ seconds; work-item ≤ 3 minutes). The unified envelope should clearly signal "this took 180s" vs "this took 2s" via `time_taken`.
- The 422-on-missing-fields contract changes: today's `WorkItemRequest` rejects empty external_ref. Once `input` is the only required field, validation moves DOWN into the dispatcher.
- `tests/unit/test_app_langgraph_helpers.py`, `test_approval_route.py`, `test_work_item_idempotency_truth.py`, `test_work_item_runner_budget.py`, `test_work_item_status_endpoint.py` all need rewrites or adapter shims.

### Change 3 — Layered test structure (last per sequence)

**Exists today**
- `tests/unit/` — flat. ~40 test files. Includes pack-shaped tests (`test_gif_tote_nodes.py`, `test_devops_health_pack.py`).
- `pytest.ini` — need to check `testpaths`.
- `tests/conftest.py` — single shared conftest.
- No `tests/unit/agent_factory/` directory.
- No `packs/<pack_id>/tests/` directory.

**To build**
- Create `tests/unit/agent_factory/`. Add `__init__.py`. Add tests:
  - `test_invoke_contract.py`: POST `/a2a/invoke` → 200 + has `session_id`; POST `/a2a/invoke-stream` → `text/event-stream`; missing required fields → 422; unknown `agent_id` → 404; `flatten_input` cases (str, dict, nested dict, list, int).
  - `test_triage_llm.py`: `TriageResult` populated from mocked LLM; LLM parse failure → graceful (no 500, warning logged); arbitrary input dict reaches the triage node without `KeyError`.
  - `test_logging_trace.py`: each graph node emits structured log entry with `{node, session_id, agent_id, work_item_id, duration_ms, status}` — assert via `caplog`.
- Create `packs/gif_tote_validation/tests/test_gif_tote_tools.py`:
  - Tests for `ticket_tools.fetch_ticket`, `update_ticket`, `resolve_ticket`, `add_work_notes`, `set_ticket_pending`.
  - Tests for `email_sender.send_merchant_outreach` (mock httpx).
  - Tests for `isam_mock.mock_isam_lookup`.
- Create `packs/devops_health_check/tests/test_devops_tools.py`:
  - Tests for `health_checks.check_ping`, `check_cpu`, `notify_oncall`, `restart_service`.
- Migrate `test_gif_tote_nodes.py` and `test_devops_health_pack.py` from `tests/unit/` into `packs/<pack_id>/tests/` (Layer B). They're already pack-shaped.
- Update `pytest.ini::testpaths` to include `packs/*/tests` and `tests/unit/agent_factory`.

**Impact / Shortcomings**
- Test discovery split MUST be verified before any other test rewrite — otherwise pack tests silently stop running in CI.
- Patching store singletons follows the AGENTS.md rule: `sys.modules["storage.<x>_store"]` — the new test files must follow this idiom.
- Total new test files: ~5 (3 framework + 2 pack). Plus ~5 file rewrites for the route consolidation.

---

## 3 — Risks, Shortcomings, Open Decisions

| # | Risk / decision needed | Status / decision |
|---|---|---|
| R1 | Breaking external contract on `/a2a/work-item/process` and `/a2a/approval/complete` | **DECIDED — hard switch.** No dual routes, no monkey-patch, no fail-over. Clean cut. Cron-poller + Concord owners must be informed before merge. |
| R2 | Idempotency depends on `external_ref` — but `input: any` may not carry one | **DECIDED — synthetic UUID OK.** Persist `kind_data.synthetic_ref=true` so observability can spot it. |
| R3 | LLM triage costs tokens on every passed request; today's regex triage is free | Spec accepts this; pre-triage rule gate still rejects out-of-scope without LLM. |
| R4 | LLM parse failure: how does the pipeline proceed? | **DECIDED — option (c): fall back to today's deterministic regex/config triage.** On LLM failure or JSON parse error, `run_llm_triage` catches the exception, logs WARNING with `traceback_id`, and the triage node continues with the regex/config output that was already populated. Two triage code paths must keep working — pack tests must exercise both branches. |
| R5 | `secrets.toml` reorganisation touches reference sites | **MITIGATED by revised approach.** Per-pack secrets.toml uses the same flat `[default.<section>]` shape — existing reference sites need ZERO changes. |
| R6 | `agent_factory/`/`storage/` confirm-gate applies to every change in Change 1, 2, 4, 5, 6 | Honoured — each file/symbol stated and "go" requested before edit (per AGENTS.md §6.1). |
| R7 | Log volume ~8× | **DECIDED — fine with volume.** |
| R8 | Existing pack triage prompts (`packs/gif_tote_validation/prompts/triage.j2`) emit a SNOW-shaped JSON, not the proposed `{intent, sop_step, evidence_fields, confidence}` shape | **DECIDED — rewrite.** Pack prompt rewritten to emit TriageResult schema. Pack-shaped tests must catch divergence. |
| R9 | Test suite has dependencies (`test_app_langgraph_helpers.py` exercises the routes that will be renamed) | Rewrite in lockstep with Change 1, not after. |
| R10 | Layer-B pack tests "must be self-contained" — current pack code calls `httpx.AsyncClient`, file IO, etc. | Adopt a `respx` or `httpx_mock` fixture; declare in each pack's `tests/conftest.py`. |
| R11 | Single `/a2a/invoke` dispatcher conflates chat (retrieval) + work-item (LangGraph) + approval (resume). Three latency tiers in one envelope | Surface `kind` in the response so clients can interpret SLAs. |
| R12 | PII risk on LLM triage — input may include sensitive data that today never reaches the gateway | Add policy doc in `secrets.toml.template` header; verify the gateway is approved for the data class. |
| R13 | Sequence places route changes (Change 1) AFTER logging (Change 4) | Correct — implement `log_step` in `common/logging.py` and `GraphBuilder._wrap()` first; routes only consume it indirectly. |
| R14 | `pytest.ini` change may need `--rootdir` / `conftest` adjustments to discover `packs/*/tests/` | Verify `pytest.ini` and add per-pack `conftest.py` if needed. |
| R15 | GET `/a2a/work-item/{external_ref}` retention | **DECIDED — keep.** Stays alongside the new `/a2a/invoke` for polling. |

---

## 4 — Execution Sequence (matches user spec; each step = one commit)

User directive: **commit each change separately**.

1. **Change 5 — Two-file secrets layering.** *(separate commit)*
   - Confirm-gated edits:
     - `agent_factory/infrastructure/secrets.toml` — remove pack-flavoured sections (`servicenow_proxy`, `gif_api`, `iqs_api`, `uber_api`, `uber_keys`, `isam_api`, gif's `slack` SSOT channel id).
     - `agent_factory/infrastructure/secrets.toml.template` — update with the new "common file" / "per-pack file" split.
     - `agent_factory/pack_loader.py` (or `registry.py`, whichever owns pack activation) — merge `packs/<pack_id>/secrets.toml` into Dynaconf at load.
   - Non-gated edits:
     - `packs/gif_tote_validation/secrets.toml` — new file containing moved sections.
     - `packs/devops_health_check/secrets.toml` — new file (minimal or empty stub).
     - `.gitignore` — add `packs/*/secrets.toml` rule.
   - Run `python3 -m pytest tests/unit/ -q`; report pass count.
   - Ask before committing.

2. **Change 6 — `flatten_input` + `InvokeRequest`.** *(separate commit)*
   - Confirm-gated edits:
     - `agent_factory/nodes/pre_triage.py` — add `flatten_input(raw) -> str` and normalisation step (extract `external_ref` if present, else synthetic UUID with `kind_data.synthetic_ref=true`; flatten input to `work_item_text`; store raw as `domain_payload`).
     - `agent_factory/api/schemas/request.py` — add `InvokeRequest{input: Any, session_id?, agent_id?, metadata?}`.
   - Run unit baseline; report pass count.
   - Ask before committing.

3. **Change 2 — LLM-driven triage.** *(separate commit)*
   - Confirm-gated edits:
     - `agent_factory/nodes/prompts/triage_base.j2` — new generic prompt with `{sop_ir}` + `{raw_input}` + `{instruction}` placeholders.
     - `agent_factory/nodes/triage_llm.py` — new adapter `run_llm_triage(state, pack) -> TriageResult` (pack prompt override → base prompt; calls `build_langchain_model_client`; parses JSON; fail behaviour per pending decision on R4).
     - `agent_factory/nodes/triage.py` — add `TriageResult` Pydantic model; call `run_llm_triage` AFTER existing regex/config pass; backfill `triage_result` on state.
   - Pack-scope edit:
     - `packs/gif_tote_validation/prompts/triage.j2` — rewrite to emit TriageResult schema (per R8 decision).
   - Run unit baseline; report pass count.
   - Ask before committing.

4. **Change 4 — `log_step` helper + graph wrapper.** *(separate commit)*
   - Confirm-gated edits:
     - `agent_factory/common/logging.py` — add `log_step(logger, node_name, *, session_id, agent_id, work_item_id, pack_id, status, duration_ms, extra=None, error_type=None, error_message=None, traceback_id=None)`; add `pack_id`/`work_item_id` contextvars.
     - `agent_factory/graph/builder.py::_wrap` — emit `started`/`completed`/`failed` log lines around every wrapped node. Preserve `GraphBubbleUp` re-raise semantics.
   - Run unit baseline; report pass count.
   - Ask before committing.

5. **Change 1 — Route consolidation (hard switch).** *(separate commit)*
   - Confirm-gated edits:
     - `agent_factory/api/routes/chat.py` — rewrite `invoke` + `invoke_stream` as dispatchers (`kind: "work_item" | "approval_callback" | "chat"`); single response envelope.
     - `app.py` — remove `app.include_router(work_item_routes.router)` and `app.include_router(approval_routes.router)` for the POST routes. Keep the GET `/a2a/work-item/{external_ref}` router import (R15 decision).
   - Non-gated edits:
     - `postman/` — update collection to reflect the new `/a2a/invoke` body shape.
   - Internal callable surface: keep `dispatch_approval` and `run_work_item_via_langgraph` importable from their current module paths — the dispatcher just calls them in-process.
   - Run unit baseline; report pass count.
   - Ask before committing.

6. **Change 3 — Test layering.** *(separate commit)*
   - Non-gated edits:
     - `tests/unit/agent_factory/__init__.py` — new.
     - `tests/unit/agent_factory/test_invoke_contract.py` — 200 on minimal valid body + `session_id`; `text/event-stream` on stream; 422 missing; 404 unknown `agent_id`; `flatten_input` cases.
     - `tests/unit/agent_factory/test_triage_llm.py` — `TriageResult` populated from mocked LLM; parse-failure path (no 500, warning logged); arbitrary dict reaches the node without `KeyError`.
     - `tests/unit/agent_factory/test_logging_trace.py` — assert each node emits structured log entry via `caplog`.
     - `packs/gif_tote_validation/tests/test_gif_tote_tools.py` — per-method tests for `ticket_tools.py`, `email_sender.py`, `isam_mock.py`.
     - `packs/devops_health_check/tests/test_devops_tools.py` — per-method tests for `health_checks.py`.
     - Migrate existing `tests/unit/test_gif_tote_nodes.py` and `tests/unit/test_devops_health_pack.py` into their packs' `tests/` directories.
     - `pytest.ini` — add `packs/*/tests` and `tests/unit/agent_factory` to `testpaths`.
   - Run **full** unit baseline; report pass count.
   - Ask before committing.

7. Final advisor() check.
8. Ask before pushing. Ask before opening a PR.

---

## 5 — Sign-Off Status

| # | Item | Status |
|---|---|---|
| 1 | External cutover plan for `/a2a/work-item/process` and `/a2a/approval/complete` | **Hard switch** (no dual routes, no monkey-patch, no fail-over) |
| 2 | Idempotency policy when `input` carries no `external_ref` | **Synthetic UUID** (with `kind_data.synthetic_ref=true`) |
| 3 | LLM triage failure behaviour | **Option (c): fall back to deterministic regex/config triage** on LLM failure or JSON parse error |
| 4 | Pack prompt override semantics | **Rewrite** the pack's `triage.j2` to emit TriageResult schema |
| 5 | GET `/a2a/work-item/{external_ref}` retention | **Keep** for polling |
| 6 | Token + log-volume budget | **Accepted** |
| 7 | Sequence (5 → 6 → 2 → 4 → 1 → 3) | **Approved** |
| 8 | Secrets layering shape | **Two flat files, same `[default.<section>]` pattern** — root `agent_factory/infrastructure/secrets.toml` + per-pack `packs/<pack_id>/secrets.toml`, merged into Dynaconf at pack load |
| 9 | Commit cadence | **One commit per change**, ask before each commit |

**All sign-off items resolved. Implementation can begin.**

— end of plan —
