from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Stop:
    stop_id: str
    name: str
    lat: float
    lon: float
    zone: str = ""


@dataclass
class RouteResult:
    route_name: str
    path: list[str]
    total_time_min: int
    total_distance_km: float
    cost: float
    walking_m: int
    transfers: int
    reliability: float
    source: str
    destination: str
