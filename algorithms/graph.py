from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "sample" / "demo_routes.json"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    delta_lat = lat2_rad - lat1_rad
    delta_lon = lon2_rad - lon1_rad

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius_km * c


def load_demo_transport_data() -> dict[str, Any]:
    with DATA_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def build_transport_graph(data: dict[str, Any] | None = None) -> dict[str, dict[str, dict[str, Any]]]:
    payload = data if data is not None else load_demo_transport_data()
    graph: dict[str, dict[str, dict[str, Any]]] = {}
    stops = payload.get("stops", [])
    stop_lookup = {stop["name"].lower(): stop for stop in stops}

    for route in payload.get("routes", []):
        route_id = route.get("route_id") or route.get("route_name")
        route_name = route.get("route_name") or route_id
        if not route_id or not route_name:
            continue
        path = route.get("stops", [])

        for index in range(len(path) - 1):
            source_name = path[index]
            target_name = path[index + 1]
            source_stop = stop_lookup.get(source_name.lower())
            target_stop = stop_lookup.get(target_name.lower())

            if source_stop is None or target_stop is None:
                continue

            distance_km = None
            try:
                source_lat = float(source_stop["lat"])
                source_lon = float(source_stop["lon"])
                target_lat = float(target_stop["lat"])
                target_lon = float(target_stop["lon"])
                if (
                    -90 <= source_lat <= 90
                    and -180 <= source_lon <= 180
                    and -90 <= target_lat <= 90
                    and -180 <= target_lon <= 180
                ):
                    distance_km = haversine_km(source_lat, source_lon, target_lat, target_lon)
            except (KeyError, TypeError, ValueError):
                pass

            graph.setdefault(source_name, {})
            graph.setdefault(target_name, {})
            edge = graph[source_name].setdefault(
                target_name,
                {
                    "route_ids": [],
                    "route_names": [],
                },
            )
            edge.setdefault("route_ids", [])
            edge.setdefault("route_names", [])
            if route_id not in edge["route_ids"]:
                edge["route_ids"].append(route_id)
            if route_name not in edge["route_names"]:
                edge["route_names"].append(route_name)
            edge["route_name"] = " / ".join(edge["route_names"]) if len(edge["route_names"]) > 1 else edge["route_names"][0]
            edge["route_id"] = edge["route_ids"][0]
            if distance_km is not None:
                edge["distance_km"] = round(distance_km, 3)
                edge["distance_basis"] = "stop_to_stop_geodesic_estimate"

            reverse_edge = graph[target_name].setdefault(
                source_name,
                {
                    "route_ids": [],
                    "route_names": [],
                },
            )
            reverse_edge.setdefault("route_ids", [])
            reverse_edge.setdefault("route_names", [])
            if route_id not in reverse_edge["route_ids"]:
                reverse_edge["route_ids"].append(route_id)
            if route_name not in reverse_edge["route_names"]:
                reverse_edge["route_names"].append(route_name)
            reverse_edge["route_name"] = " / ".join(reverse_edge["route_names"]) if len(reverse_edge["route_names"]) > 1 else reverse_edge["route_names"][0]
            reverse_edge["route_id"] = reverse_edge["route_ids"][0]
            if distance_km is not None:
                reverse_edge["distance_km"] = round(distance_km, 3)
                reverse_edge["distance_basis"] = "stop_to_stop_geodesic_estimate"

    return graph
