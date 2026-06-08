"""Deterministic grouping for the DEW Restriction sub-SOP.

One callable tool:

``group_dew_restrictions``
    Walks the ``forxn`` array returned by the DEW sync-ops service
    (GET /offer/read/id/{offerId}) and groups restriction entries by
    each individual restriction path.

    Each ``forxn`` entry carries ``path`` and ``state`` as *lists*
    (not single strings) plus ``tag``, ``type``, ``storeId``.  We
    explode each entry across its ``path`` list so the output is one
    row per distinct restriction path, with all applicable state
    codes unioned and sorted.

    Output rows are sorted by path so the closure renders
    deterministically.
"""
from __future__ import annotations

from typing import Any, Iterable, Optional


def group_dew_restrictions(forxn: Optional[Iterable[Any]] = None,
                           **_: Any) -> dict[str, Any]:
    """Group DEW ``forxn`` entries by path.

    Returns:
      {
        "outcome": "DEW_RESTRICTIONS_PRESENT" | "DEW_NO_RESTRICTIONS",
        "groups":  [{"path": "<path>", "states": ["AR", "CA", ...]}, ...]
      }
    """
    path_to_states: dict[str, set[str]] = {}

    for entry in (forxn or []):
        if not isinstance(entry, dict):
            continue
        paths = entry.get("path") or []
        states = entry.get("state") or []
        if isinstance(paths, str):
            paths = [paths]
        if isinstance(states, str):
            states = [states]
        if not isinstance(paths, (list, tuple)):
            continue
        clean_states = [
            str(s).strip().upper()
            for s in (states or [])
            if s is not None and str(s).strip()
        ]
        for raw_path in paths:
            if raw_path is None:
                continue
            path = str(raw_path).strip()
            if not path:
                continue
            path_to_states.setdefault(path, set()).update(clean_states)

    groups = [
        {"path": p, "states": sorted(path_to_states[p])}
        for p in sorted(path_to_states)
    ]

    return {
        "outcome": "DEW_RESTRICTIONS_PRESENT" if groups else "DEW_NO_RESTRICTIONS",
        "groups":  groups,
    }


__all__ = ["group_dew_restrictions"]
