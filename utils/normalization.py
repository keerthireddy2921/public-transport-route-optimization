from __future__ import annotations


def normalize_preference(value: str | None) -> str:
    mapping = {
        "fastest": "fastest",
        "shortest": "shortest",
        "cheapest": "cheapest",
        "fewest transfers": "fewest transfers",
        "less walking": "less walking",
        "most reliable": "most reliable",
        "fewest_transfers": "fewest transfers",
        "less_walking": "less walking",
        "most_reliable": "most reliable",
    }
    return mapping.get((value or "").strip().lower(), "fastest")
