# matbot Multi-Agents

> Walmart's multi-agent factory monorepo — a pack-agnostic LangGraph runtime that boots any number of declaratively defined SOP agents from a single image.

This repo is the **runtime + factory substrate**. Each agent is an SOP **Pack** under [`packs/`](packs/): a directory of YAML + JSON + Jinja2 templates with **zero business logic in Python**. The runtime (`agent_factory/` + `app.py`) loads every pack at startup, compiles each into a LangGraph, and serves it.

The companion repo [`MERCHSPACE/sop-normalizer`](https://gecgithub01.walmart.com/MERCHSPACE/sop-normalizer) generates these packs from human-authored SOP documents. The two repos communicate via the **SOP-IR schema** ([`agent_factory/ir/models.py`](agent_factory/ir/models.py)) — that's the contract.

---

## Shipped packs

| Pack | Status | What it does |
|---|---|---|
| [`gif_tote_validation`](packs/gif_tote_validation/) | Production | Autonomous incident resolution for GIF Tote dimension validation — polls ServiceNow, validates item dimensions, routes or fixes tickets. See the [pack README](packs/gif_tote_validation/README.md) for full architecture and operator runbook. |
| [`devops_health_check`](packs/devops_health_check/) | Toy / reference | Synthetic toy pack proving the substrate is genuinely pack-agnostic — pings a host, checks CPU, recommends a service restart (requires approval). |

---

## Repo layout

```
matbot-multi-agents/
├── agent_factory/        # Pack-agnostic substrate (loader, registry, graph factory, nodes, integrations)
│   ├── ir/               # SOP-IR Pydantic models — the schema shared with sop-normalizer
│   ├── pack/             # Canonical SOP-Pack namespace (loader, models, registry, prompts)
│   ├── pack_loader.py    # Loads pack.yaml + tools.yaml + sop-ir.json + policy.yaml + prompts/templates
│   ├── pack_models/      # Pydantic schemas split by YAML file: pack.py / tools.py / policy.py
│   ├── registry.py       # PackRegistry — discover_and_load_all() + PACK_ID env var filter
│   ├── runtime/          # Canonical LangChain runtime namespace (builder, chat, model_client)
│   ├── graph/            # LangGraph state schema + edges + factory
│   ├── nodes/            # Reusable nodes (triage, diagnostic, decision, action, closure, evidence, …)
│   └── integrations/     # Slack, ServiceNow, Concord approval, LLM gateway
├── packs/                # One subdirectory per agent — declarative config only
│   ├── _example/         #   scaffold copied by the normalizer
│   ├── gif_tote_validation/
│   └── devops_health_check/
├── storage/              # Postgres-backed incident/audit/work-item/session stores + migrations
├── app.py                # FastAPI entry — routes A2A + webhooks to pack-resolved graphs
├── tests/                # pytest suite — 931 passing on main
├── Dockerfile            # python:3.12-slim production image
└── requirements.txt
```

---

## How a pack is wired

Every `pack.yaml` declares its runtime entry points; the loader resolves them with `importlib` at startup so the runtime never imports a specific pack by name:

```yaml
# packs/<id>/pack.yaml
runtime:
  graph_builder: "packs.<id>.graph:build_<id>_graph"
  state_factory: "packs.<id>.state:empty_incident_state"
```

`app.py` walks `pack_registry.list_packs()` at boot, calls each pack's `graph_builder`, and registers the compiled LangGraph under the pack's id. Per-request, the state factory is resolved the same way. Default-pack failures are fatal; sibling-pack failures degrade individually so one broken pack can't take down the rest.

---

## Single-pack child-process deployments

When the runtime ships as one pod per pack, each pod sets `PACK_ID=<pack_id>` on itself. The registry honours that env var and narrows discovery to a single pack:

```bash
PACK_ID=gif_tote_validation uvicorn app:app --host 0.0.0.0 --port 8000
```

Empty / whitespace / typo'd `PACK_ID` values are rejected; the charset guard (`^[a-z][a-z0-9_]*$`) keeps shell-injection payloads out of log aggregators.

---

## Local quickstart

```bash
git clone https://gecgithub01.walmart.com/item-ops/matbot-multi-agents.git
cd matbot-multi-agents

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run the full test suite (931 passing on main)
pytest tests/

# Run the API locally — boots ALL packs under packs/
uvicorn app:app --reload --port 8000
```

For a deep dive into the GIF Tote pack specifically (architecture, decision rules, runbooks, configuration, troubleshooting) see [`packs/gif_tote_validation/README.md`](packs/gif_tote_validation/README.md).

---

## Adding a new pack

1. Author the SOP document (Confluence / docx / markdown).
2. Run [`sop-normalizer`](https://gecgithub01.walmart.com/MERCHSPACE/sop-normalizer) against it to scaffold `packs/<your_id>/` (pack.yaml, tools.yaml, sop-ir.json, policy.yaml, prompts/, templates/, eval_cases.json).
3. Implement the pack's `graph_builder` and `state_factory` Python entry points (these stay pack-private — typically `packs/<id>/graph.py` and `packs/<id>/state.py`).
4. Declare them in `pack.yaml`:
   ```yaml
   runtime:
     graph_builder: "packs.<id>.graph:build_<id>_graph"
     state_factory: "packs.<id>.state:empty_incident_state"
   ```
5. Commit. The next boot of `app.py` (or `PackRegistry.discover_and_load_all(force=True)`) picks it up automatically.

---

## CI / quality gates

- `pytest tests/` — 931 tests, ~6s on dev hardware
- `sonar-project.properties` — Sonar key `agent-factory`
- Dockerfile builds the slim production image; tests run in a `test` stage upstream

---

## History

This repo was migrated from `MERCHSPACE/gif-tote-validation-agent` after a refactor that turned a single-pack agent into a config-driven multi-pack factory. Full commit history is preserved.
