import pytest
import folium

from algorithms.dijkstra import dijkstra_path
from algorithms.graph import build_transport_graph, haversine_km, load_demo_transport_data
from algorithms.scoring import score_route, normalize_metric, route_weight
from services.recommendation_service import RecommendationService
from services.route_service import RouteService


@pytest.fixture
def sample_graph():
    return {
        "A": {"B": {"distance_km": 2.0, "travel_time_min": 10, "cost": 15.0, "walking_m": 100, "transfers": 0, "reliability": 0.9, "route": "Bus 5"},
              "C": {"distance_km": 5.0, "travel_time_min": 20, "cost": 20.0, "walking_m": 300, "transfers": 1, "reliability": 0.8, "route": "Bus 9"}},
        "B": {"D": {"distance_km": 3.0, "travel_time_min": 12, "cost": 10.0, "walking_m": 0, "transfers": 0, "reliability": 0.85, "route": "Bus 5"}},
        "C": {"D": {"distance_km": 2.0, "travel_time_min": 14, "cost": 12.0, "walking_m": 100, "transfers": 0, "reliability": 0.75, "route": "Bus 9"}},
        "D": {}
    }


def test_dijkstra_shortest_path(sample_graph):
    route = dijkstra_path(sample_graph, "A", "D", preference="fastest")
    assert route["path"] == ["A", "B", "D"]
    assert route["total_time_min"] == 22


def test_score_route_normalizes_values():
    route = {
        "distance_km": 2.0,
        "travel_time_min": 10,
        "cost": 15.0,
        "walking_m": 100,
        "transfers": 0,
        "reliability": 0.9,
    }
    score = score_route(route, preference="fastest")
    assert score >= 0
    assert score <= 1.5


def test_route_weight_reduces_to_positive_number():
    route = {
        "distance_km": 2.0,
        "travel_time_min": 10,
        "cost": 15.0,
        "walking_m": 100,
        "transfers": 0,
        "reliability": 0.9,
    }
    weight = route_weight(route, "shortest")
    assert weight > 0


def test_route_service_recommends_fastest_route():
    service = RouteService()
    graph = {
        "A": {"B": {"distance_km": 1.0, "travel_time_min": 5, "cost": 10.0, "walking_m": 50, "transfers": 0, "reliability": 0.8, "route": "R1"},
              "C": {"distance_km": 3.0, "travel_time_min": 8, "cost": 5.0, "walking_m": 500, "transfers": 1, "reliability": 0.7, "route": "R2"}},
        "B": {"D": {"distance_km": 1.0, "travel_time_min": 7, "cost": 8.0, "walking_m": 0, "transfers": 0, "reliability": 0.9, "route": "R1"}},
        "C": {"D": {"distance_km": 1.0, "travel_time_min": 10, "cost": 5.0, "walking_m": 100, "transfers": 0, "reliability": 0.6, "route": "R2"}},
        "D": {}
    }
    recommendation = service._recommend_route(graph, "A", "D", "fastest")
    assert recommendation["route_name"] in {"R1", "R2"}
    assert recommendation["total_time_min"] >= 0


def test_route_names_match_dataset_values():
    service = RouteService()
    path = ["Secunderabad Junction", "Lakdikapul", "Koti", "Charminar"]
    route_names = service._route_names_for_path(path)
    valid_route_names = {route["route_name"] for route in service.data["routes"]}
    assert set(route_names).issubset(valid_route_names)
    assert {"Bus 17", "Bus 5"}.issubset(set(route_names))


def test_dataset_direct_journey_uses_one_actual_bus():
    service = RouteService()
    result = service.find_route("Secunderabad Junction", "Charminar", "shortest")
    route = result["recommended_route"]

    assert route["route_name"] == "Bus 5"
    assert route["transfers"] == 0
    assert route["legs"] == [{
        "route_name": "Bus 5",
        "mode": "bus",
        "path": ["Secunderabad Junction", "Paradise", "MG Bus Station", "Koti", "Charminar"],
        "transfer_at": None,
    }]


def test_dataset_connection_shows_actual_buses_and_transfer_stop():
    service = RouteService()
    result = service.find_route("Charminar", "Nampally", "shortest")
    route = result["recommended_route"]

    assert [leg["route_name"] for leg in route["legs"]] == ["Bus 5", "Bus 17"]
    assert route["transfers"] == 1
    assert route["legs"][0]["transfer_at"] == "Koti"
    assert route["legs"][0]["path"] == ["Charminar", "Koti"]
    assert route["legs"][1]["path"] == ["Koti", "Nampally"]


def test_route_aware_dijkstra_finds_dataset_transfer():
    service = RouteService()
    route = service._recommend_route(service.graph, "Charminar", "Nampally", "shortest")

    assert route["route_name"] == "Bus 5 / Bus 17"
    assert route["transfers"] == 1
    assert route["transfer_stops"] == ["Koti"]


def test_exact_dataset_stop_name_is_not_geocoded_elsewhere():
    service = RouteService()

    assert service.location_service.resolve_to_stop("Nampally", service.data["stops"])["name"] == "Nampally"


def test_dataset_multi_transfer_alternative_uses_valid_routes_and_stops():
    service = RouteService()
    result = service.find_route("Charminar", "Nampally", "shortest")
    alternative = next(route for route in result["alternatives"] if route["transfers"] == 2)
    route_lookup = {route["route_name"]: route["stops"] for route in service.data["routes"]}

    assert [leg["route_name"] for leg in alternative["legs"]] == ["Bus 5", "Bus 218", "Bus 17"]
    assert alternative["transfers"] == 2
    for index, leg in enumerate(alternative["legs"]):
        assert leg["route_name"] in route_lookup
        assert all(stop in route_lookup[leg["route_name"]] for stop in leg["path"])
        if index < len(alternative["legs"]) - 1:
            transfer_stop = leg["transfer_at"]
            next_route = alternative["legs"][index + 1]["route_name"]
            assert transfer_stop in route_lookup[leg["route_name"]]
            assert transfer_stop in route_lookup[next_route]


def test_partial_stop_search_returns_only_dataset_stops():
    service = RouteService()
    matching = service.location_service.search_stop_names("M", service.data["stops"])

    assert matching == ["MG Bus Station", "Charminar", "Nampally", "Ameerpet", "Madhapur"]


def test_nonexistent_stop_is_rejected_instead_of_snapping_to_nearest():
    service = RouteService()

    with pytest.raises(ValueError, match="No matching place found"):
        service.location_service.resolve_to_stop("Atlantis", service.data["stops"])


def test_recommendation_scoring_uses_aggregate_distance():
    routes = [
        {"route_name": "Longer", "total_distance_km": 3.0, "transfers": 0},
        {"route_name": "Shorter", "total_distance_km": 1.0, "transfers": 0},
    ]

    ranked = RecommendationService().rank_routes(routes, "shortest")

    assert ranked[0]["route_name"] == "Shorter"


def test_fewest_transfers_is_primary_ranking_criterion():
    routes = [
        {"route_name": "Shorter with transfer", "total_distance_km": 1.0, "transfers": 1},
        {"route_name": "Direct", "total_distance_km": 8.0, "transfers": 0},
    ]
    ranked = RecommendationService().rank_routes(routes, "fewest transfers")
    assert ranked[0]["route_name"] == "Direct"


def test_journey_stop_count_counts_transfer_stop_once():
    service = RouteService()
    route = service.find_route("Charminar", "Nampally", "shortest")["recommended_route"]
    assert route["path"] == ["Charminar", "Koti", "Nampally"]
    assert route["stop_count"] == 3


def test_demo_graph_does_not_invent_cost_time_or_reliability():
    graph = build_transport_graph(load_demo_transport_data())
    edge = graph["Secunderabad Junction"]["Paradise"]

    assert "cost" not in edge
    assert "travel_time_min" not in edge
    assert "reliability" not in edge


def test_sample_dataset_integrity_audit():
    data = load_demo_transport_data()
    stops = data["stops"]
    routes = data["routes"]
    stop_names = [stop["name"] for stop in stops]
    stop_ids = [stop["stop_id"] for stop in stops]
    route_names = [route["route_name"] for route in routes]
    route_ids = [route["route_id"] for route in routes]

    assert len(stop_names) == len(set(stop_names))
    assert len(stop_ids) == len(set(stop_ids))
    assert len(route_names) == len(set(route_names))
    assert len(route_ids) == len(set(route_ids))
    assert all(-90 <= float(stop["lat"]) <= 90 for stop in stops)
    assert all(-180 <= float(stop["lon"]) <= 180 for stop in stops)
    assert all(stop_name in set(stop_names) for route in routes for stop_name in route["stops"])
    assert all("distance_km" not in route for route in routes)


def test_recommended_distance_is_sum_of_route_segment_geodesics():
    service = RouteService()
    route = service.find_route("Secunderabad Junction", "Charminar", "shortest")["recommended_route"]
    expected_distance = sum(
        haversine_km(
            service.stop_lookup[start.lower()]["lat"],
            service.stop_lookup[start.lower()]["lon"],
            service.stop_lookup[end.lower()]["lat"],
            service.stop_lookup[end.lower()]["lon"],
        )
        for start, end in zip(route["path"], route["path"][1:])
    )

    assert route["total_distance_km"] == pytest.approx(expected_distance, abs=0.02)


def test_route_id_is_used_when_dataset_has_no_route_name():
    data = {
        "stops": [
            {"stop_id": "A", "name": "Origin", "lat": 17.0, "lon": 78.0},
            {"stop_id": "B", "name": "Terminus", "lat": 17.1, "lon": 78.1},
        ],
        "routes": [{"route_id": "R-42", "mode": "bus", "stops": ["Origin", "Terminus"]}],
    }
    service = RouteService(data=data)
    result = service.find_route("Origin", "Terminus", "shortest")

    assert result["recommended_route"]["route_name"] == "R-42"


def test_same_stop_search_is_rejected():
    service = RouteService()

    with pytest.raises(ValueError, match="Source and destination are the same"):
        service.find_route("Koti", "Koti", "shortest")


def test_missing_coordinates_do_not_create_distance_or_map():
    data = {
        "stops": [
            {"stop_id": "A", "name": "Origin"},
            {"stop_id": "B", "name": "Terminus"},
        ],
        "routes": [{"route_id": "R-7", "route_name": "Bus 7", "mode": "bus", "stops": ["Origin", "Terminus"]}],
    }
    service = RouteService(data=data)
    route = service.find_route("Origin", "Terminus", "shortest")["recommended_route"]

    assert route["total_distance_km"] is None
    assert service.build_map_for_route(route) is None


def test_connecting_route_map_contains_separate_legs_and_transfer_marker():
    service = RouteService()
    route = service.find_route("Charminar", "Nampally", "shortest")["recommended_route"]
    map_obj = service.build_map_for_route(route)

    assert map_obj is not None
    assert sum(isinstance(item, folium.PolyLine) for item in map_obj._children.values()) == 2
    assert any(isinstance(item, folium.CircleMarker) for item in map_obj._children.values())
