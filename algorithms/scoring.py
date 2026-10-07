from __future__ import annotations


def normalize_metric(value: float, scale: float) -> float:
    if scale <= 0:
        return 0.0
    return max(0.0, min(1.0, value / scale))


def score_route(route: dict, preference: str = "fastest") -> float:
    if not route:
        return 0.0

    pref = (preference or "fastest").strip().lower()
    weights = {
        "fastest": {"time": 0.45, "distance": 0.10, "cost": 0.08, "walking": 0.08, "transfers": 0.10, "reliability": 0.19},
        "shortest": {"time": 0.10, "distance": 0.75, "cost": 0.0, "walking": 0.0, "transfers": 0.15, "reliability": 0.0},
        "cheapest": {"time": 0.08, "distance": 0.12, "cost": 0.48, "walking": 0.08, "transfers": 0.10, "reliability": 0.14},
        "fewest transfers": {"time": 0.0, "distance": 0.15, "cost": 0.0, "walking": 0.0, "transfers": 0.85, "reliability": 0.0},
        "less walking": {"time": 0.10, "distance": 0.08, "cost": 0.06, "walking": 0.52, "transfers": 0.12, "reliability": 0.12},
        "most reliable": {"time": 0.12, "distance": 0.08, "cost": 0.06, "walking": 0.08, "transfers": 0.08, "reliability": 0.58},
    }

    metric_values = {
        "time": route.get("total_time_min", route.get("travel_time_min")),
        "distance": route.get("total_distance_km", route.get("distance_km")),
        "cost": route.get("cost"),
        "walking": route.get("walking_m"),
        "transfers": route.get("transfers"),
        "reliability": route.get("reliability"),
    }
    required_metric = "distance" if pref == "shortest" else "transfers" if pref == "fewest transfers" else None
    if required_metric and metric_values[required_metric] is None:
        return float("inf")
    scales = {"time": 90, "distance": 25, "cost": 80, "walking": 2000, "transfers": 3, "reliability": 1}
    chosen = weights.get(pref, weights["shortest"])
    available_weights = {
        key: weight for key, weight in chosen.items()
        if weight > 0 and metric_values[key] is not None
    }
    weight_total = sum(available_weights.values())
    if weight_total == 0:
        return 0.0

    total = sum(
        weight / weight_total * normalize_metric(float(metric_values[key]), scales[key])
        for key, weight in available_weights.items()
    )
    return round(total, 4)


def route_weight(route: dict, preference: str = "fastest") -> float:
    return score_route(route, preference)
