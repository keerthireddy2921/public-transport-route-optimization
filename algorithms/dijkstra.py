from __future__ import annotations

import heapq
from typing import Any


def edge_weight(edge: dict[str, Any], preference: str) -> float:
    preference_key = (preference or "fastest").strip().lower()
    weight_map = {
        "fastest": float(edge.get("travel_time_min", 1)),
        "shortest": float(edge.get("distance_km", 0.1)),
        "cheapest": float(edge.get("cost", 0.1)),
        "fewest transfers": float(edge.get("transfers", 0) * 25 + edge.get("travel_time_min", 1) * 0.5),
        "less walking": float(edge.get("walking_m", 0) * 0.02 + edge.get("travel_time_min", 1) * 0.5),
        "most reliable": max(1.0, (1.0 - float(edge.get("reliability", 0.5))) * 100 + edge.get("travel_time_min", 1) * 0.5),
    }
    return float(weight_map.get(preference_key, weight_map["fastest"]))


def _summarize_path(graph: dict[str, dict[str, dict[str, Any]]], path: list[str]) -> dict[str, Any]:
    metric_values: dict[str, list[float]] = {
        "distance_km": [],
        "travel_time_min": [],
        "cost": [],
        "walking_m": [],
        "transfers": [],
        "reliability": [],
    }
    route_names = []

    for index in range(len(path) - 1):
        current = path[index]
        nxt = path[index + 1]
        edge = graph.get(current, {}).get(nxt)
        if edge is None:
            continue
        for metric in metric_values:
            if edge.get(metric) is not None:
                metric_values[metric].append(float(edge[metric]))
        route_name = edge.get("route_name") or edge.get("route")
        if route_name:
            route_names.append(route_name)

    reliability_values = metric_values["reliability"]
    reliability = (
        round(sum(reliability_values) / len(reliability_values), 3)
        if reliability_values else None
    )
    return {
        "path": path,
        "route_name": " / ".join(dict.fromkeys(route_names)) if route_names else None,
        "total_distance_km": round(sum(metric_values["distance_km"]), 2) if metric_values["distance_km"] else None,
        "total_time_min": sum(metric_values["travel_time_min"]) if metric_values["travel_time_min"] else None,
        "cost": sum(metric_values["cost"]) if metric_values["cost"] else None,
        "walking_m": sum(metric_values["walking_m"]) if metric_values["walking_m"] else None,
        "transfers": int(sum(metric_values["transfers"])) if metric_values["transfers"] else 0,
        "reliability": reliability,
    }


def dijkstra_path(graph: dict[str, dict[str, dict[str, Any]]], start: str, end: str, preference: str = "fastest") -> dict[str, Any] | None:
    if start == end:
        return {
            "path": [start],
            "route_name": None,
            "total_distance_km": 0.0,
            "total_time_min": None,
            "cost": None,
            "walking_m": None,
            "transfers": 0,
            "reliability": None,
        }

    queue: list[tuple[float, str]] = [(0.0, start)]
    distances: dict[str, float] = {start: 0.0}
    previous: dict[str, str | None] = {start: None}

    while queue:
        current_cost, current_node = heapq.heappop(queue)
        if current_cost > distances.get(current_node, float("inf")):
            continue
        if current_node == end:
            break

        for neighbor, edge in graph.get(current_node, {}).items():
            alt_cost = current_cost + edge_weight(edge, preference)
            if alt_cost < distances.get(neighbor, float("inf")):
                distances[neighbor] = alt_cost
                previous[neighbor] = current_node
                heapq.heappush(queue, (alt_cost, neighbor))

    if end not in distances:
        return None

    path: list[str] = []
    current: str | None = end
    while current is not None:
        path.append(current)
        current = previous.get(current)
    path.reverse()

    return _summarize_path(graph, path)


def dijkstra_route_path(
    routes: list[dict[str, Any]],
    graph: dict[str, dict[str, dict[str, Any]]],
    start: str,
    end: str,
    preference: str = "fastest",
) -> dict[str, Any] | None:
    """Find a route while tracking the boarded route at every stop."""
    if start == end:
        return None

    route_by_id = {}
    for route in routes:
        route_id = route.get("route_id") or route.get("route_name")
        route_label = route.get("route_name") or route_id
        if route_id and route_label:
            route_by_id[str(route_id)] = {**route, "_display_name": str(route_label)}

    routes_by_stop: dict[str, list[str]] = {}
    for route_id, route in route_by_id.items():
        for stop in route.get("stops", []):
            routes_by_stop.setdefault(stop, []).append(route_id)

    start_states = [(start, route_id) for route_id in routes_by_stop.get(start, [])]
    if not start_states:
        return None

    preference_key = (preference or "fastest").strip().lower()
    transfer_penalties = {
        "fastest": 8.0,
        "shortest": 0.5,
        "cheapest": 0.01,
        "fewest transfers": 25.0,
        "less walking": 0.5,
        "most reliable": 5.0,
    }
    transfer_penalty = transfer_penalties.get(preference_key, transfer_penalties["fastest"])

    distances = {state: 0.0 for state in start_states}
    previous: dict[tuple[str, str], tuple[tuple[str, str], str] | None] = {
        state: None for state in start_states
    }
    queue: list[tuple[float, str, str]] = [
        (0.0, stop, route_id) for stop, route_id in start_states
    ]
    goal: tuple[str, str] | None = None

    while queue:
        current_cost, current_stop, current_route_id = heapq.heappop(queue)
        state = (current_stop, current_route_id)
        if current_cost > distances.get(state, float("inf")):
            continue
        if current_stop == end:
            goal = state
            break

        route = route_by_id[current_route_id]
        route_stops = route.get("stops", [])
        stop_index = route_stops.index(current_stop)
        ride_neighbors = []
        if stop_index > 0:
            ride_neighbors.append(route_stops[stop_index - 1])
        if stop_index + 1 < len(route_stops):
            ride_neighbors.append(route_stops[stop_index + 1])

        transitions: list[tuple[tuple[str, str], str, float]] = []
        for neighbor in ride_neighbors:
            edge = graph.get(current_stop, {}).get(neighbor)
            if edge is not None:
                transitions.append(((neighbor, current_route_id), "ride", edge_weight(edge, preference)))

        for next_route_id in routes_by_stop.get(current_stop, []):
            if next_route_id != current_route_id:
                transitions.append(((current_stop, next_route_id), "transfer", transfer_penalty))

        for next_state, action, weight in transitions:
            next_cost = current_cost + weight
            if next_cost < distances.get(next_state, float("inf")):
                distances[next_state] = next_cost
                previous[next_state] = (state, action)
                heapq.heappush(queue, (next_cost, next_state[0], next_state[1]))

    if goal is None:
        return None

    actions: list[tuple[str, str, str, str]] = []
    state = goal
    while previous[state] is not None:
        prior_state, action = previous[state]
        actions.append((action, prior_state[0], state[0], state[1]))
        state = prior_state
    actions.reverse()

    legs: list[dict[str, Any]] = []
    path = [start]
    total_distance = 0.0
    distance_available = True
    time_values = []
    cost_values = []
    reliability_values = []
    for action, from_stop, to_stop, route_id in actions:
        route_name = route_by_id[route_id]["_display_name"]
        if action == "transfer":
            if legs:
                legs[-1]["transfer_at"] = from_stop
            continue

        if not legs or legs[-1]["route_name"] != route_name:
            legs.append({
                "route_name": route_name,
                "mode": route_by_id[route_id].get("mode", "transit"),
                "path": [from_stop],
                "transfer_at": None,
            })
        legs[-1]["path"].append(to_stop)
        path.append(to_stop)

        edge = graph[from_stop][to_stop]
        if edge.get("distance_km") is None:
            distance_available = False
        else:
            total_distance += float(edge["distance_km"])
        if edge.get("travel_time_min") is not None:
            time_values.append(int(edge["travel_time_min"]))
        if edge.get("cost") is not None:
            cost_values.append(float(edge["cost"]))
        if edge.get("reliability") is not None:
            reliability_values.append(float(edge["reliability"]))

    if not legs:
        return None

    route_names = list(dict.fromkeys(leg["route_name"] for leg in legs))
    return {
        "route_name": " / ".join(route_names),
        "path": path,
        "legs": legs,
        "total_distance_km": round(total_distance, 2) if distance_available else None,
        "total_time_min": sum(time_values) if time_values else None,
        "cost": sum(cost_values) if cost_values else None,
        "walking_m": None,
        "transfers": max(0, len(legs) - 1),
        "reliability": round(sum(reliability_values) / len(reliability_values), 3) if reliability_values else None,
        "transfer_stops": [leg["transfer_at"] for leg in legs if leg.get("transfer_at")],
    }
