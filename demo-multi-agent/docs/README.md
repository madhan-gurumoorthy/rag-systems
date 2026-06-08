# GIF Tote Validation Agent — Documentation

**Project:** GIF Tote Validation — Autonomous Incident Resolution System  
**Version:** 1.0.0  
**Team:** MerchantOps - Item Setup/Maintenance  
**Last Updated:** April 2026

---

## Documents

| Document | Description |
|----------|-------------|
| [Architecture](./GIF_TOTE_ARCHITECTURE.md) | Comprehensive system architecture — executive summary, problem statement, solution design, agent pipeline, tool layer, decision matrix, integrations, API endpoints, data model, deployment, and roadmap |
| [Architecture Diagrams (ASCII)](./architecture-diagrams.md) | Text-based diagrams for all key flows — suitable for Markdown rendering, PRs, and terminal review |

## Diagrams (draw.io)

Open these `.drawio` files with [draw.io](https://app.diagrams.net/) or the VS Code Draw.io Integration extension.

| Diagram | Description |
|---------|-------------|
| [High-Level Architecture](./diagrams/01-high-level-architecture.drawio) | End-to-end system overview — ingress channels, gateway, pre-triage, pipeline, persistence |
| [Agent Pipeline](./diagrams/02-agent-pipeline.drawio) | 5-agent incident pipeline flow with tool bindings and data handoffs |
| [Integrations Map](./diagrams/03-integrations-map.drawio) | All external system connections — ServiceNow, GIF API, IQS, Uber, iSAM, SMTP, Slack |
| [Decision Matrix](./diagrams/04-decision-matrix.drawio) | Deterministic rule engine — diagnostic outcomes to runbook card routing |
| [Data Model](./diagrams/05-data-model.drawio) | PostgreSQL schema — incident_log, audit_trail, conversation_state, sessions |
| [Dashboard & API](./diagrams/06-dashboard-api.drawio) | REST API endpoints, dashboard data flows, and webhook processing |

## Quick Links

- **Main README:** [`../README.md`](../README.md)
- **Pack Config:** [`../packs/gif_tote_validation/pack.yaml`](../packs/gif_tote_validation/pack.yaml)
- **Tool Manifest:** [`../packs/gif_tote_validation/tools.yaml`](../packs/gif_tote_validation/tools.yaml)
- **Policy Config:** [`../packs/gif_tote_validation/policy.yaml`](../packs/gif_tote_validation/policy.yaml)
- **SOP IR (Decision Rules):** [`../packs/gif_tote_validation/sop-ir.json`](../packs/gif_tote_validation/sop-ir.json)
- **API Spec:** generated live by FastAPI at `GET /openapi.json` (browse via `GET /docs`)
- **Postman Collection:** [`../postman/GIF_Tote_Validation_Agent.postman_collection.json`](../postman/GIF_Tote_Validation_Agent.postman_collection.json)
