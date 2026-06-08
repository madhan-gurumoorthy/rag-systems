#!/usr/bin/env python3
"""Export the FastAPI app's OpenAPI document to ``specs/api-spec.json``.

The R2C contract-test runner consumes ``specs/api-spec.json`` to probe
the deployed service. Hand-maintaining that file drifts from the route
handlers under ``agent_factory/api/routes/``; this script writes the
spec directly from ``app.openapi()`` so the two surfaces cannot diverge.

Run as::

    python3 scripts/export_api_spec.py

Exits non-zero if the resulting JSON cannot be re-parsed.

The CI drift-gate (``api_spec_drift`` flow in ``looper.yml``) re-runs
this script and fails the build when the working tree's
``specs/api-spec.json`` does not match the freshly generated one — so
every PR that touches routes or schemas must also include the
regenerated spec.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Make the repo root importable so ``from app import app`` resolves
# whether the script is invoked from the repo root or anywhere else.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app import app  # noqa: E402 — path mutation must run before the import


def build_spec() -> dict:
    """Return the OpenAPI document produced by FastAPI."""
    return app.openapi()


def serialize(spec: dict) -> str:
    """Format the spec with tab indentation and a trailing newline.

    Tab indentation keeps the committed file's diff readable; matching
    the format here keeps every regeneration a no-op when nothing
    changed.
    """
    return json.dumps(spec, indent="\t", ensure_ascii=False) + "\n"


def main() -> int:
    spec = build_spec()
    payload = serialize(spec)

    # Round-trip parse — if Pydantic's example payload contains a value
    # that json cannot encode, fail loudly here, not in CI.
    json.loads(payload)

    target = REPO_ROOT / "specs" / "api-spec.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(payload, encoding="utf-8")
    print(f"Wrote {target.relative_to(REPO_ROOT)} ({len(spec.get('paths', {}))} paths)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
