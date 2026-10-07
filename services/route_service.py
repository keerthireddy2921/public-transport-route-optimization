from __future__ import annotations

from typing import Any

import folium

from algorithms.dijkstra import dijkstra_path, dijkstra_route_path
from algorithms.graph import build_transport_graph, load_demo_transport_data
from services.location_service import LocationService
from services.recommendation_service import RecommendationService
from utils.normalization import normalize_preference


class RouteService:
    def __init__(self, location_service: LocationService | None = None, data: dict[str, Any] | None = None):
        self.location_service = location_service or LocationService()
        self.data = data if data is not None else load_demo_transport_data()
        self.graph = build_transport_graph(self.data)
        self.stop_lookup = {stop["name"].lower(): stop for stop in self.data.get("stops", [])}
        self.recommendation_service = RecommendationService()

    def _route_segment(self, route_stops: list[str], start_stop: str, end_stop: str) -> list[str]:
        if start_stop == end_stop:
            return [start_stop]
        if start_stop not in route_stops or end_stop not in route_stops:
            return []

        start_index = route_stops.index(start_stop)
        end_index = route_stops.index(end_stop)
        if start_index <= end_index:
            return route_stops[start_index:end_index + 1]
        return list(reversed(route_stops[end_index:start_index + 1]))

    def _route_names_for_path(self, path: list[str]) -> list[str]:
        valid_route_names = {
            route.get("route_name") for route in self.data.get("routes", []) if route.get("route_name")
        }
        route_names = []
        for start_stop, end_stop in zip(path, path[1:]):
            edge = self.graph.get(start_stop, {}).get(end_stop, {})
            names = edge.get("route_names") or [edge.get("route_name") or edge.get("route")]
            for route_name in names:
                if route_name in valid_route_names and route_name not in route_names:
                    route_names.append(route_name)
        return route_names

    @staticmethod
    def _route_label(route: dict[str, Any]) -> str:
        return str(route.get("route_name") or route.get("route_id") or "").strip()

    def _build_sequence_paths(self, route_sequence: list[str], source: str, destination: str) -> list[dict[str, Any]]:
        route_lookup = {
            self._route_label(route): route
            for route in self.data.get("routes", [])
            if self._route_label(route)
        }
        if not route_sequence:
            return []

        built_paths: list[dict[str, Any]] = []

        def visit(index: int, current_stop: str, legs: list[dict[str, Any]]) -> None:
            route_name = route_sequence[index]
            route = route_lookup.get(route_name, {})
            route_stops = route.get("stops", [])
            if current_stop not in route_stops:
                return

            if index == len(route_sequence) - 1:
                final_segment = self._route_segment(route_stops, current_stop, destination)
                if len(final_segment) < 2:
                    return
                final_legs = legs + [{
                    "route_name": route_name,
                    "mode": route.get("mode", "transit"),
                    "path": final_segment,
                    "transfer_at": None,
                }]
                combined_path = [final_legs[0]["path"][0]]
                for leg in final_legs:
                    combined_path.extend(leg["path"][1:])
                built_paths.append({
                    "route_name": " / ".join(leg["route_name"] for leg in final_legs),
                    "path": combined_path,
                    "legs": final_legs,
                    "transfers": len(final_legs) - 1,
                })
                return

            next_route_stops = route_lookup.get(route_sequence[index + 1], {}).get("stops", [])
            shared_stops = [stop for stop in route_stops if stop in next_route_stops]
            for transfer_stop in shared_stops:
                segment = self._route_segment(route_stops, current_stop, transfer_stop)
                if len(segment) < 2:
                    continue
                transfer_legs = legs + [{
                    "route_name": route_name,
                    "mode": route.get("mode", "transit"),
                    "path": segment,
                    "transfer_at": transfer_stop,
                }]
                visit(index + 1, transfer_stop, transfer_legs)

        visit(0, source, [])
        return built_paths

    def _candidate_route_sequences(self, source: str, destination: str, max_hops: int | None = None) -> list[list[str]]:
        route_entries = self.data.get("routes", [])
        route_limit = max_hops if max_hops is not None else len(route_entries)
        direct_candidates: list[list[str]] = []
        for route in route_entries:
            stops = route.get("stops", [])
            route_label = self._route_label(route)
            if route_label and source in stops and destination in stops:
                direct_candidates.append([route_label])
        if direct_candidates:
            return direct_candidates

        candidates: list[list[str]] = []
        queue: list[list[str]] = []
        for route in route_entries:
            route_label = self._route_label(route)
            if route_label and source in route.get("stops", []):
                queue.append([route_label])

        visited: set[tuple[str, ...]] = set()

        while queue:
            route_sequence = queue.pop(0)
            key = tuple(route_sequence)
            if key in visited:
                continue
            visited.add(key)

            last_route_name = route_sequence[-1]
            last_route = next((route for route in route_entries if self._route_label(route) == last_route_name), None)
            if last_route is None:
                continue

            last_stops = last_route.get("stops", [])
            if destination in last_stops:
                candidates.append(route_sequence)
                continue

            if len(route_sequence) >= route_limit:
                continue

            for route in route_entries:
                route_label = self._route_label(route)
                if not route_label or route_label in route_sequence:
                    continue
                shared_stops = set(last_stops) & set(route.get("stops", []))
                if shared_stops:
                    queue.append(route_sequence + [route_label])

        unique_candidates: list[list[str]] = []
        seen_sequences: set[tuple[str, ...]] = set()
        for candidate in candidates:
            key = tuple(candidate)
            if key not in seen_sequences:
                unique_candidates.append(candidate)
                seen_sequences.add(key)
        return unique_candidates

    def _summarize_candidate(self, candidate: dict[str, Any]) -> dict[str, Any] | None:
        route_name = candidate.get("route_name") or candidate.get("route_id")
        if not route_name:
            return None
        path = candidate.get("path", [])
        legs = candidate.get("legs", [])
        transfer_stops = [leg.get("transfer_at") for leg in legs if leg.get("transfer_at")]

        total_distance = 0.0
        distance_available = True

        for index in range(len(path) - 1):
            current = path[index]
            nxt = path[index + 1]
            edge = self.graph.get(current, {}).get(nxt)
            if edge is None:
                return None
            if edge.get("distance_km") is None:
                distance_available = False
            else:
                total_distance += float(edge["distance_km"])

        return {
            "route_name": route_name,
            "path": path,
            "legs": legs,
            "total_distance_km": round(total_distance, 2) if distance_available else None,
            "total_time_min": None,
            "cost": None,
            "walking_m": None,
            "transfers": max(0, len(legs) - 1),
            # Stop count means distinct stop-to-stop ride segments, including
            # the boarding stop. A transfer stop appears in both legs but only
            # once in the journey-level count.
            "stop_count": len(set(path)),
            "reliability": None,
            "transfer_stops": transfer_stops,
        }

    def _collect_alternative_routes(self, start: str, end: str, max_routes: int = 5) -> list[dict[str, Any]]:
        route_sequences = self._candidate_route_sequences(start, end)
        candidates = []
        for sequence in route_sequences:
            for built in self._build_sequence_paths(sequence, start, end):
                summarized = self._summarize_candidate(built)
                if summarized is not None:
                    candidates.append(summarized)

        unique_candidates = {}
        for candidate in candidates:
            key = tuple((leg["route_name"], tuple(leg["path"])) for leg in candidate["legs"])
            unique_candidates[key] = candidate
        return list(unique_candidates.values())

    def _recommend_route(self, graph: dict[str, dict[str, dict[str, Any]]], start: str, end: str, preference: str) -> dict[str, Any] | None:
        if graph is not self.graph:
            return dijkstra_path(graph, start, end, preference)
        return dijkstra_route_path(self.data.get("routes", []), graph, start, end, preference)

    def find_route(self, source_query: str, destination_query: str, preference: str) -> dict[str, Any]:
        source_stop = self.location_service.resolve_to_stop(source_query, self.data.get("stops", []))
        destination_stop = self.location_service.resolve_to_stop(destination_query, self.data.get("stops", []))

        if source_stop["name"].lower() == destination_stop["name"].lower():
            raise ValueError("Source and destination are the same location. Please choose different places.")

        normalized_preference = normalize_preference(preference)
        if normalized_preference not in {"shortest", "fewest transfers"}:
            raise ValueError(
                "This dataset supports shortest estimated distance and fewest transfers only; "
                "verified time, fare, walking, and reliability data are unavailable."
            )
        candidates = self._collect_alternative_routes(source_stop["name"], destination_stop["name"])
        if not candidates:
            return {
                "recommended_route": None,
                "alternatives": [],
                "explanation": "No public-transport route was found between these locations.",
            }

        ranked = self.recommendation_service.rank_routes(candidates, normalized_preference)
        recommended = ranked[0]

        return {
            "recommended_route": recommended,
            "alternatives": ranked[1:4],
            "explanation": self.recommendation_service.explain_route(recommended, normalized_preference),
            "source_stop": source_stop,
            "destination_stop": destination_stop,
            "ranking_criteria": normalized_preference,
        }

    def build_map_for_route(self, route: dict[str, Any] | None):
        if route is None or not route.get("path"):
            return None

        coordinates = []
        for stop_name in route["path"]:
            stop = self.stop_lookup.get(stop_name.lower())
            if stop is None or stop.get("lat") is None or stop.get("lon") is None:
                return None
            coordinates.append([stop["lat"], stop["lon"]])

        if not coordinates:
            return None

        center_lat = sum(coord[0] for coord in coordinates) / len(coordinates)
        center_lon = sum(coord[1] for coord in coordinates) / len(coordinates)
        map_obj = folium.Map(location=[center_lat, center_lon], zoom_start=12)

        first_stop = self.stop_lookup.get(route["path"][0].lower())
        last_stop = self.stop_lookup.get(route["path"][-1].lower())
        if first_stop is not None:
            folium.Marker([first_stop["lat"], first_stop["lon"]], tooltip="Source", popup=first_stop["name"]).add_to(map_obj)
        if last_stop is not None:
            folium.Marker([last_stop["lat"], last_stop["lon"]], tooltip="Destination", popup=last_stop["name"]).add_to(map_obj)

        legs = route.get("legs", [])
        colors = ["#1f77b4", "#d95f02", "#238b45", "#756bb1"]
        if legs:
            for index, leg in enumerate(legs):
                leg_coordinates = [
                    [self.stop_lookup[stop_name.lower()]["lat"], self.stop_lookup[stop_name.lower()]["lon"]]
                    for stop_name in leg["path"]
                ]
                if len(leg_coordinates) >= 2:
                    folium.PolyLine(
                        leg_coordinates,
                        color=colors[index % len(colors)],
                        weight=5,
                        opacity=0.85,
                        tooltip=leg.get("route_name", "Route"),
                    ).add_to(map_obj)
                transfer_stop = leg.get("transfer_at")
                if transfer_stop:
                    transfer = self.stop_lookup[transfer_stop.lower()]
                    folium.CircleMarker(
                        [transfer["lat"], transfer["lon"]],
                        radius=7,
                        color="#111111",
                        fill=True,
                        fill_color="#ffffff",
                        tooltip=f"Transfer: {transfer_stop}",
                    ).add_to(map_obj)
        else:
            folium.PolyLine(coordinates, color="#1f77b4", weight=5, opacity=0.8).add_to(map_obj)
        return map_obj
