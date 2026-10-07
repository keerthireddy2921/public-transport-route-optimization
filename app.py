from typing import Any

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from streamlit_folium import st_folium

from services.location_service import LocationService
from services.route_service import RouteService

load_dotenv()


def _as_metric_rows(routes: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for route in routes:
        distance = route.get("total_distance_km")
        rows.append(
            {
                "Route": route.get("route_name", "N/A"),
                "Estimated geodesic distance": f"~{distance:.1f} km" if distance is not None else "Unavailable",
                "Transfers": route.get("transfers", 0),
                "Stops": route.get("stop_count", len(set(route.get("path", [])))),
                "Fare": "Unavailable (no fare data)",
                "Travel time": "Unavailable (no schedule data)",
                "Transfer stops": ", ".join(route.get("transfer_stops", [])) or "None",
            }
        )
    return pd.DataFrame(rows)


st.set_page_config(page_title="Public Transport & Route Optimization", layout="wide")
st.title("Public Transport and Route Optimization")
st.caption(
    "Demo/sample dataset with unverified route provenance. Route labels are shown exactly as stored. "
    "Distance is estimated from stop-to-stop geodesic segments; road distance and timetable, fare, "
    "walking, and reliability data are not provided."
)

if "route_result" not in st.session_state:
    st.session_state.route_result = None

location_service = LocationService()
route_service = RouteService(location_service=location_service)


def render_route_result(result: dict[str, Any] | None) -> None:
    if result and result.get("error"):
        st.error(result["error"])
        return
    if not result or not result.get("recommended_route"):
        st.info("No valid public transport route was found between these locations.")
        return

    recommended = result["recommended_route"]
    st.subheader("Recommended Route")
    st.markdown(f"### {recommended.get('route_name', 'Route')}")
    distance = recommended.get("total_distance_km")
    col1, col2, col3 = st.columns(3)
    col1.metric("Estimated geodesic distance", f"~{distance:.1f} km" if distance is not None else "Unavailable")
    col2.metric("Transfers", recommended.get("transfers", 0))
    col3.metric("Stops", recommended.get("stop_count", len(set(recommended.get("path", [])))))
    st.caption("Distance sums geodesic estimates between consecutive stops on the selected route; it is not road distance.")
    st.caption("Travel time, fare, walking distance, and reliability are unavailable in this dataset. Missing values are not estimated.")

    st.write("Route-by-route breakdown")
    legs = recommended.get("legs", [])
    if legs:
        st.write(f"Source: {legs[0]['path'][0]}")
        for index, leg in enumerate(legs):
            route_name = leg.get("route_name") or leg.get("route_id") or "Unidentified route"
            mode = leg.get("mode", "bus").lower()
            if mode == "bus":
                label = f"🚌 Bus {index + 1}: {route_name}"
            elif mode == "metro":
                label = f"🚇 Metro: {route_name}"
            else:
                label = f"{mode.title()}: {route_name}" if mode != "transit" else route_name
            st.write(label)
            st.caption("Stops: " + " → ".join(leg.get("path", [])))
            transfer_at = leg.get("transfer_at")
            if transfer_at:
                st.write(f"Change at: {transfer_at}")
        st.write(f"Destination: {legs[-1]['path'][-1]}")
    else:
        st.write(f"Route: {recommended.get('route_name') or 'Unidentified route'}")

    st.write("Why this route?")
    st.info(result.get("explanation", "Route selected based on the chosen preference."))

    alternatives = result.get("alternatives", [])
    if alternatives:
        st.subheader("Alternative Routes")
        st.dataframe(_as_metric_rows([recommended, *alternatives]), use_container_width=True, hide_index=True)

    map_obj = route_service.build_map_for_route(recommended)
    if map_obj is not None:
        st.subheader("Map")
        st_folium(map_obj, width=1200, height=500)
    else:
        st.info("Map unavailable because coordinates are missing for one or more route stops.")

    st.subheader("Route sequence")
    st.write(" → ".join(recommended.get("path", [])))


with st.sidebar:
    st.header("Route Inputs")
    source_query = st.text_input("Find source place", placeholder="Type a stop name", key="source_query")
    source_options = location_service.search_stop_names(source_query)
    if source_query.strip() and not source_options:
        st.caption("No matching place found in the available stops.")
    source = st.selectbox(
        "Source stop",
        source_options,
        index=None,
        placeholder="Select a matching stop",
        key="source_stop",
    )

    destination_query = st.text_input("Find destination place", placeholder="Type a stop name", key="destination_query")
    destination_options = location_service.search_stop_names(destination_query)
    if destination_query.strip() and not destination_options:
        st.caption("No matching place found in the available stops.")
    destination = st.selectbox(
        "Destination stop",
        destination_options,
        index=None,
        placeholder="Select a matching stop",
        key="destination_stop",
    )

    preference = st.selectbox(
        "Optimization preference",
        ["shortest", "fewest transfers"],
        format_func=lambda value: {
            "shortest": "Shortest estimated distance",
            "fewest transfers": "Fewest transfers",
        }[value],
    )
    search_button = st.button("Find route")
    clear_button = st.button("Clear results")

    if search_button:
        st.session_state.route_result = None
        if not source_query.strip() or not destination_query.strip():
            st.session_state.route_result = {"error": "Search for and select both a source and a destination stop."}
        elif not source_options:
            st.session_state.route_result = {"error": "No matching place found for the source in the available stops."}
        elif not destination_options:
            st.session_state.route_result = {"error": "No matching place found for the destination in the available stops."}
        elif source not in source_options or destination not in destination_options:
            st.session_state.route_result = {"error": "Select a source and destination from the matching dataset stops."}
        elif source == destination:
            st.session_state.route_result = {"error": "Source and destination must be different stops."}
        else:
            try:
                st.session_state.route_result = route_service.find_route(source, destination, preference)
            except ValueError as exc:
                st.session_state.route_result = {"error": str(exc)}

    if clear_button:
        st.session_state.route_result = None

if st.session_state.route_result is not None:
    render_route_result(st.session_state.route_result)
else:
    st.info("Enter a source and destination to find the most suitable public-transport route.")
