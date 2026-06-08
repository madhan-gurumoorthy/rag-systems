"""Jira handler — declarative JIRA REST API v2 operations over httpx.

Resolves connection details from Dynaconf via ``spec.jira_connection``,
renders JQL/project/field templates against the call params, and drives
the JIRA REST API v2.

Operations (``spec.jira_operation``):

  * ``search``       — JQL search (``POST /rest/api/2/search``)
  * ``get``          — fetch one issue by key
  * ``create``       — create issue (auto-injects project + issuetype)
  * ``update``       — partial field update
  * ``transition``   — move an issue between workflow states
  * ``add_comment``  — append a comment

Auth resolution:

  * If ``username`` + ``api_token`` are both set → HTTP Basic.
  * If only ``api_token`` is set → Bearer (PAT) auth.

The handler reaches back through ``executor._enrich_params_from_templates``
and ``executor._get_ssl_context`` — both stay as instance methods on
:class:`~agent_factory.tools.executor.ToolExecutor` because tests patch
them directly.
"""
from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING

from ._base import ToolHandler
from ..executor import _render_template, logger

if TYPE_CHECKING:  # pragma: no cover
    from ..executor import ToolExecutor
    from ..pack_models import ToolSpec


class JiraHandler(ToolHandler):
    type_name = "jira"

    async def execute(
        self,
        *,
        tool_id: str,
        spec: "ToolSpec",
        params: dict[str, Any],
        executor: "ToolExecutor",
    ) -> dict[str, Any]:
        if spec.type != "jira":
            return {"error": f"Tool '{tool_id}' is not a jira tool"}

        import httpx
        from ..response_processors import apply_processor
        from agent_factory.infrastructure.settings import get_config

        config = get_config()
        conn_cfg = (
            getattr(config, spec.jira_connection, None)
            if spec.jira_connection else None
        )
        if not conn_cfg:
            return {"error": f"JIRA connection '{spec.jira_connection}' not configured"}

        enriched = executor._enrich_params_from_templates(params, [
            spec.jira_jql_template,
            spec.jira_project,
            spec.jira_transition_name,
            *[str(v) for v in spec.jira_fields_template.values()],
        ])

        base_url = getattr(conn_cfg, "base_url", "") or getattr(conn_cfg, "JIRA_BASE_URL", "")
        if not base_url:
            return {"error": "JIRA base_url not configured"}

        # Build auth — JIRA typically uses basic auth or PAT
        import base64
        username = getattr(conn_cfg, "username", "") or getattr(conn_cfg, "JIRA_USER", "")
        token = getattr(conn_cfg, "api_token", "") or getattr(conn_cfg, "JIRA_API_TOKEN", "")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if username and token:
            encoded = base64.b64encode(f"{username}:{token}".encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"
        elif token:
            headers["Authorization"] = f"Bearer {token}"

        operation = spec.jira_operation
        verify = executor._get_ssl_context()

        try:
            async with httpx.AsyncClient(timeout=spec.timeout_seconds, verify=verify) as client:
                if operation == "search":
                    jql = _render_template(spec.jira_jql_template, enriched)
                    resp = await client.post(
                        f"{base_url}/rest/api/2/search",
                        json={"jql": jql, "maxResults": 50},
                        headers=headers,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    # Normalize: extract issues array
                    issues = data.get("issues", [])
                    result_data = {"issues": issues, "total": data.get("total", 0), "count": len(issues)}

                elif operation == "get":
                    issue_key = enriched.get(spec.jira_issue_key_param, "")
                    if not issue_key:
                        return {"error": f"Missing issue key param '{spec.jira_issue_key_param}'"}
                    resp = await client.get(
                        f"{base_url}/rest/api/2/issue/{issue_key}",
                        headers=headers,
                    )
                    resp.raise_for_status()
                    result_data = resp.json()

                elif operation == "create":
                    fields = {}
                    if spec.jira_fields_template:
                        fields_str = json.dumps(spec.jira_fields_template)
                        fields_str = _render_template(fields_str, enriched)
                        fields = json.loads(fields_str)
                    # Inject project and issue type
                    project = _render_template(spec.jira_project, enriched) if spec.jira_project else ""
                    if project:
                        fields.setdefault("project", {"key": project})
                    if spec.jira_issue_type:
                        fields.setdefault("issuetype", {"name": spec.jira_issue_type})
                    resp = await client.post(
                        f"{base_url}/rest/api/2/issue",
                        json={"fields": fields},
                        headers=headers,
                    )
                    resp.raise_for_status()
                    result_data = resp.json()

                elif operation == "update":
                    issue_key = enriched.get(spec.jira_issue_key_param, "")
                    if not issue_key:
                        return {"error": f"Missing issue key param '{spec.jira_issue_key_param}'"}
                    fields = {}
                    if spec.jira_fields_template:
                        fields_str = json.dumps(spec.jira_fields_template)
                        fields_str = _render_template(fields_str, enriched)
                        fields = json.loads(fields_str)
                    resp = await client.put(
                        f"{base_url}/rest/api/2/issue/{issue_key}",
                        json={"fields": fields},
                        headers=headers,
                    )
                    resp.raise_for_status()
                    result_data = {"key": issue_key, "updated": True}

                elif operation == "transition":
                    issue_key = enriched.get(spec.jira_issue_key_param, "")
                    if not issue_key:
                        return {"error": f"Missing issue key param '{spec.jira_issue_key_param}'"}
                    transition_name = _render_template(spec.jira_transition_name, enriched)
                    # First get available transitions
                    trans_resp = await client.get(
                        f"{base_url}/rest/api/2/issue/{issue_key}/transitions",
                        headers=headers,
                    )
                    trans_resp.raise_for_status()
                    transitions = trans_resp.json().get("transitions", [])
                    target = next(
                        (t for t in transitions if t["name"].lower() == transition_name.lower()),
                        None,
                    )
                    if not target:
                        avail = [t["name"] for t in transitions]
                        return {"error": f"Transition '{transition_name}' not found. Available: {avail}"}
                    resp = await client.post(
                        f"{base_url}/rest/api/2/issue/{issue_key}/transitions",
                        json={"transition": {"id": target["id"]}},
                        headers=headers,
                    )
                    resp.raise_for_status()
                    result_data = {"key": issue_key, "transitioned_to": transition_name}

                elif operation == "add_comment":
                    issue_key = enriched.get(spec.jira_issue_key_param, "")
                    if not issue_key:
                        return {"error": f"Missing issue key param '{spec.jira_issue_key_param}'"}
                    comment_body = enriched.get("comment", enriched.get("body", ""))
                    resp = await client.post(
                        f"{base_url}/rest/api/2/issue/{issue_key}/comment",
                        json={"body": comment_body},
                        headers=headers,
                    )
                    resp.raise_for_status()
                    result_data = resp.json()

                else:
                    return {"error": f"Unknown JIRA operation: {operation}"}

            result = apply_processor(
                spec.response.processor, result_data, spec.response, params,
            )
            return result

        except httpx.HTTPStatusError as e:
            status_code = str(e.response.status_code)
            error_outcomes = spec.response.error_outcomes
            outcome = error_outcomes.get(status_code) or error_outcomes.get("default")
            if outcome:
                return {"outcome": outcome, "error": f"JIRA HTTP {status_code}", **params}
            body_preview = e.response.text[:500] if e.response.text else ""
            return {"error": f"JIRA HTTP {status_code}: {body_preview}", **params}
        except Exception as e:  # noqa: BLE001 — surface to caller
            error_outcomes = spec.response.error_outcomes
            outcome = error_outcomes.get("default")
            if outcome:
                return {"outcome": outcome, "error": str(e), **params}
            logger.error(f"jira tool '{tool_id}' failed: {e}", exc_info=True)
            return {"error": str(e), **params}


__all__ = ["JiraHandler"]
