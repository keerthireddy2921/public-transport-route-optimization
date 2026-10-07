from __future__ import annotations


def is_non_empty_text(value: str | None) -> bool:
    return bool(value and value.strip())


def safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def is_valid_coordinate(lat: float, lon: float) -> bool:
    return -90 <= safe_float(lat) <= 90 and -180 <= safe_float(lon) <= 180
