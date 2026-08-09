from __future__ import annotations

from dataclasses import dataclass

from backend.domain.entities.place import Place


@dataclass
class RankedPlace:
    place: Place
    score: float
    distance_m: float
