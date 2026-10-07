from __future__ import annotations

from algorithms.scoring import route_weight
from utils.normalization import normalize_preference


class RecommendationService:
    def rank_routes(self, routes: list[dict], preference: str) -> list[dict]:
        normalized = normalize_preference(preference)
        ranked = []
        for route in routes:
            if not route:
                continue
            route_copy = dict(route)
            route_copy["score"] = route_weight(route_copy, normalized)
            ranked.append(route_copy)

        # These preferences describe a single primary objective. Use the other
        # available metric only as a deterministic tie-breaker; a weighted score
        # can otherwise label a route with more transfers as "fewest transfers".
        if normalized == "fewest transfers":
            ranked.sort(key=lambda route: (
                route.get("transfers") if route.get("transfers") is not None else float("inf"),
                route.get("total_distance_km") if route.get("total_distance_km") is not None else float("inf"),
                route.get("route_name", ""),
            ))
        else:
            ranked.sort(key=lambda route: (
                route.get("total_distance_km") if route.get("total_distance_km") is not None else float("inf"),
                route.get("transfers") if route.get("transfers") is not None else float("inf"),
                route.get("route_name", ""),
            ))
        return ranked

    def explain_route(self, route: dict, preference: str) -> str:
        normalized = normalize_preference(preference)
        route_name = route.get("route_name", "This route")
        distance = route.get("total_distance_km", 0.0)
        transfers = route.get("transfers", 0)

        if normalized == "fastest":
            reason = "Verified travel-time data is unavailable, so this route was not ranked by speed."
        elif normalized == "shortest":
            if distance is None:
                reason = f"{route_name} is a valid route, but distance data is unavailable for ranking."
            else:
                reason = f"{route_name} is recommended for its lowest estimated geodesic stop-to-stop distance of about {distance:.1f} km. Road distance is not included in the dataset."
        elif normalized == "cheapest":
            reason = "Fare data is unavailable, so this route was not ranked by cost."
        elif normalized == "fewest transfers":
            reason = f"{route_name} is recommended because it involves {transfers} transfer(s), which is the lowest for the current route set."
        elif normalized == "less walking":
            reason = "Walking-distance data is unavailable, so this route was not ranked by walking distance."
        else:
            reason = "Reliability data is unavailable, so this route was not ranked by reliability."

        return reason
