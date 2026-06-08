"""Utility: navigate nested dicts/lists using IQS dot-notation paths."""
import re
from typing import Any, Optional


def get_nested_value(data: Any, path: str) -> Optional[Any]:
    """
    Navigate a nested dict/list using a dot-notation path with array indices.

    Strips a leading 'x.' prefix (IQS root notation), then walks the structure.
    Returns None if any segment is missing or out of bounds.

    Examples:
        get_nested_value(data, "x.payload.offers[0].offer.endDate")
        get_nested_value(data, "x.payload.product.assets.values[3].properties.assetType")
    """
    if not data or not path:
        return None

    if path.startswith("x."):
        path = path[2:]

    parts = _parse_path(path)
    current = data

    for part in parts:
        if current is None:
            return None
        if isinstance(part, int):
            if isinstance(current, list) and 0 <= part < len(current):
                current = current[part]
            else:
                return None
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            return None

    return current


def _parse_path(path: str) -> list:
    """Parse 'payload.offers[0].offer.endDate' into ['payload','offers',0,'offer','endDate']."""
    parts = []
    for segment in path.split("."):
        match = re.match(r'^(\w+)\[(\d+)\]$', segment)
        if match:
            parts.append(match.group(1))
            parts.append(int(match.group(2)))
        else:
            parts.append(segment)
    return parts
