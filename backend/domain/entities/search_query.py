from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SearchQuery:
    lat: float
    lng: float
    radius_m: int
    query_text: str
