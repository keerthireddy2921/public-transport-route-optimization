# Public Transport and Route Optimization

A Streamlit-based project prototype that recommends public-transport routes using a graph-based algorithm and a small, unverified sample dataset. Place names resemble Hyderabad, but the data does not establish Hyderabad service coverage.

## Overview

Users select source and destination stops from dataset-backed partial-match suggestions. The application prefers a route that directly serves both stops; otherwise, it searches route-to-route transfers and shows each route leg and interchange stop.

## Features

- Case-insensitive partial stop search and validated stop selection
- Ranking by shortest estimated geodesic distance or fewest transfers
- Route-aware Dijkstra search over stop/route states
- Alternative route comparison
- Route explanation generated from computed values
- Folium map with per-route legs and transfer markers
- Demo / sample transport data for academic demonstration
- Safe validation and error handling for invalid inputs

## Architecture

- `app.py` – Streamlit front-end
- `algorithms/` – graph and routing logic
- `services/` – route, location, and recommendation services
- `models/` – transport domain models
- `data/sample/` – demo transport dataset
- `tests/` – route and scoring validation

## Data

The only included source is `data/sample/demo_routes.json`, labeled demo/sample and without source provenance. Its route names and stop relationships are used exactly as written, but they are not verified real-world service information. The file provides stop coordinates and route stop sequences; it does not provide route distance, schedules, fares, walking distances, or reliability values.

## Routing and optimization

The graph uses stops as nodes and dataset route segments as edges. Route-aware Dijkstra tracks both the current stop and boarded route so transfers are explicit. Route stops are treated as traversable in either direction because the demo schema has no direction or schedule fields; this assumption is unsuitable for real service planning. “Shortest” ranks estimated geodesic distance first and “fewest transfers” ranks transfer count first; the other available metric breaks ties. Distance is the sum of haversine distances between consecutive route stops, not road-network distance. Journey stop count is the number of distinct stops, counting a transfer stop once. The app does not show invented travel times, fares, walking distances, or reliability scores.

## Verified scope and gaps

| Requirement | Current status |
| --- | --- |
| Origin/destination selection and validation | Implemented against the local sample data |
| Route recommendation | Implemented for estimated distance or transfers; not timetable-aware |
| Alternatives and comparison | Distinct route/leg sequences; comparison shows available metrics and unavailable time/fare |
| Per-leg route details and stop/transfer counts | Implemented; transfer stop counted once in journey summary |
| Fare and travel-time estimates | Unavailable because no source data exists; never fabricated |
| Route map | Sample coordinates as straight geodesic segments, not road geometry |
| Transfer wait/walking details | Unavailable because no schedule or walking data exists |
| Production city coverage | Blocked on selecting a target city and obtaining verified, licensed data |

This is a Streamlit prototype, not the Next.js/Python API/Supabase baseline in the project brief. The bundled demo fixture does not justify adding a database or a second frontend/backend. Revisit architecture when a real feed and deployment scope are selected.

## Running the app

1. Create a virtual environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the app:
   ```bash
   streamlit run app.py
   ```

## Testing

```bash
pytest -q
```

Tests cover direct and transfer routes, ranking, route/data integrity, unavailable values, and map geometry. If Python and pytest are not installed, install `requirements.txt` in a virtual environment before running the command.

## Limitations

- The demo dataset has no provenance and is not verified Hyderabad operations data; route labels are dataset values, not claims of real service.
- The dataset contains no road distances, timetables, fares, walking distances, or reliability data; corresponding metrics are unavailable.
- The map uses the included stop coordinates and displays geodesic segments, not road geometry.

## Future enhancements

- GTFS import support
- Real-time delays and disruptions
- Accessibility-aware routing
- ML-based travel-time or crowding prediction
