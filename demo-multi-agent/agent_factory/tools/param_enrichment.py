"""Parameter enrichment + SSL-context helpers for declarative tools.

Four utilities live here:

* :func:`enrich_params_from_templates` — resolves ``{{KEY}}`` placeholders
  in an arbitrary list of template strings against Dynaconf config.
* :func:`enrich_params_from_config`   — resolves ``{{KEY}}`` placeholders
  across all template fields of an :class:`http_api` :class:`~..pack_models.ToolSpec`
  (``url_template``, ``headers``, ``query_params``, ``body_template`` and
  ``auth.extra_headers``).
* :func:`get_ssl_context`             — builds an :mod:`ssl` context from
  the configured CA bundle, falling back to ``None`` (httpx default) when
  the bundle is unset or unloadable.  Never returns ``False`` — that would
  silently disable certificate validation.
* :func:`build_kafka_ssl`             — builds an :mod:`ssl` context for
  Kafka mTLS from explicit CA / cert / key paths.

The :class:`~agent_factory.tools.executor.ToolExecutor` keeps instance-method
shims (``_enrich_params_from_templates``, ``_enrich_params_from_config``,
``_get_ssl_context``, ``_build_kafka_ssl``) that delegate here.  Tests
patch the executor-bound symbols via ``patch.object(ex, "_get_ssl_context",
...)`` and call them directly via ``ex._build_kafka_ssl(...)``; the shims
keep those contracts intact while the heavy lifting lives in this module
where it can be unit-tested in isolation.

``_get_config_value`` and ``_TEMPLATE_REF_RE`` are lazy-imported from
:mod:`.executor` inside the function bodies — module-level imports would
form a cycle (``executor`` imports this module to populate the shims).
"""
from __future__ import annotations

import json
import re
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from ..pack_models import ToolSpec


# Local regex — intentionally *without* ``\s*`` so it mirrors the
# original inline pattern used by ``_enrich_params_from_templates``.
# The config-template variant (``_enrich_params_from_config``) uses
# ``_TEMPLATE_REF_RE`` from :mod:`.executor`, which tolerates whitespace.
_INLINE_TEMPLATE_REF_RE = re.compile(r"\{\{(\w+)\}\}")


def enrich_params_from_templates(
    params: dict, templates: list[str],
) -> dict[str, Any]:
    """Resolve ``{{KEY}}`` config references in a list of template strings.

    Scans each template for ``{{KEY}}`` placeholders not already present in
    ``params`` and resolves them from Dynaconf via
    :func:`agent_factory.tools.executor._get_config_value`.  Returns a new
    dict — ``params`` is never mutated.
    """
    from .executor import _get_config_value

    enriched = dict(params)
    all_refs: set[str] = set()
    for tmpl in templates:
        if tmpl:
            all_refs.update(_INLINE_TEMPLATE_REF_RE.findall(tmpl))
    for ref in all_refs:
        if ref not in enriched:
            val = _get_config_value(ref)
            if val:
                enriched[ref] = val
    return enriched


def enrich_params_from_config(params: dict, spec: "ToolSpec") -> dict:
    """Inject config values into template params for an http_api spec.

    For http_api tools, ``url_template``, ``headers``, ``query_params``,
    ``body_template`` AND ``auth.extra_headers`` may reference config
    values like ``{{SET_API_ENDPOINT}}``.  This function resolves those
    from Dynaconf so pack YAML can reference secrets without embedding
    them.
    """
    from .executor import _TEMPLATE_REF_RE, _get_config_value

    enriched = dict(params)
    # Find all {{KEY}} references across all template fields
    all_refs = set(_TEMPLATE_REF_RE.findall(spec.url_template))
    for key in spec.headers.values():
        all_refs.update(_TEMPLATE_REF_RE.findall(key))
    for key in spec.query_params.values():
        all_refs.update(_TEMPLATE_REF_RE.findall(key))
    if spec.body_template:
        all_refs.update(_TEMPLATE_REF_RE.findall(json.dumps(spec.body_template)))
    # Also scan auth extra_headers for config references
    if spec.auth and spec.auth.extra_headers:
        for val in spec.auth.extra_headers.values():
            all_refs.update(_TEMPLATE_REF_RE.findall(val))

    for ref in all_refs:
        if ref not in enriched:
            # Try to resolve from config
            val = _get_config_value(ref)
            if val:
                enriched[ref] = val
    return enriched


def get_ssl_context():
    """Return an SSL context loaded from the configured CA bundle.

    Falls back to ``None`` (httpx default — system trust store) when the
    bundle path is not configured or cannot be loaded.  Never returns
    ``False`` because ``verify=False`` silently disables certificate
    validation and must be an explicit, intentional opt-in.
    """
    from .executor import logger

    try:
        from agent_factory.infrastructure.settings import get_config
        config = get_config()
        ca_bundle = getattr(config, "LIGHTRAG_REQUESTS_CA_BUNDLE", "")
        if ca_bundle:
            import ssl
            ctx = ssl.create_default_context()
            ctx.load_verify_locations(ca_bundle)
            return ctx
    except Exception as exc:
        logger.warning(
            "Could not load CA bundle for SSL context; falling back to system trust store: %s",
            exc,
        )
    return None  # use httpx default (system trust store)


def build_kafka_ssl(cafile: str, certfile: str, keyfile: str):
    """Build an SSL context for Kafka mTLS.

    ``cafile`` is the CA bundle path.  ``certfile`` and ``keyfile`` are
    the client cert / key — both must be provided for mTLS, otherwise the
    context is server-auth only (handy for SASL_SSL setups).
    """
    import ssl
    ctx = ssl.create_default_context(cafile=cafile)
    if certfile and keyfile:
        ctx.load_cert_chain(certfile=certfile, keyfile=keyfile)
    return ctx


__all__ = [
    "enrich_params_from_templates",
    "enrich_params_from_config",
    "get_ssl_context",
    "build_kafka_ssl",
]
