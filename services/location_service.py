from __future__ import annotations

from typing import Any

from algorithms.graph import load_demo_transport_data
from utils.validation import is_non_empty_text


class LocationService:
    def __init__(self, stops: list[dict[str, Any]] | None = None):
        self.stops = stops if stops is not None else load_demo_transport_data().get("stops", [])

    def search_stop_names(self, query: str, stops: list[dict[str, Any]] | None = None) -> list[str]:
        available_stops = stops if stops is not None else self.stops
        if not is_non_empty_text(query):
            return list(dict.fromkeys(stop["name"] for stop in available_stops if stop.get("name")))

        normalized_query = query.strip().casefold()
        return list(dict.fromkeys(
            stop["name"]
            for stop in available_stops
            if stop.get("name") and normalized_query in stop["name"].casefold()
        ))

    def lookup_location(self, query: str) -> dict[str, Any]:
        if not is_non_empty_text(query):
            raise ValueError("Please provide a valid source or destination.")

        cleaned = query.strip()
        normalized_query = cleaned.casefold()
        exact_stop = next((stop for stop in self.stops if normalized_query == stop["name"].casefold()), None)
        if exact_stop is not None:
            return exact_stop

        matching_names = self.search_stop_names(cleaned)
        if len(matching_names) == 1:
            return next(stop for stop in self.stops if stop["name"] == matching_names[0])
        if matching_names:
            raise ValueError(f"Multiple stops match '{query}'. Select one of: {', '.join(matching_names)}.")
        raise ValueError(f"No matching place found in the available transport stops for '{query}'.")

    def resolve_to_stop(self, query: str, stops: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        candidates = stops if stops is not None else self.stops
        if not candidates:
            raise ValueError("No transport stops are available in the demo dataset.")
        lookup = LocationService(candidates)
        return lookup.lookup_location(query)
