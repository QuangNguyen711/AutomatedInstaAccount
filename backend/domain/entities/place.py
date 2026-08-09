from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Photo:
    url: str
    is_good: bool | None = None


@dataclass
class Review:
    text: str
    author: str | None = None
    rating: int | None = None
    posted_at: datetime | None = None
    embedding: list[float] | None = None


@dataclass
class Place:
    place_id: str
    name: str
    address: str
    lat: float
    lng: float
    maps_url: str
    rating: float | None = None
    review_count: int | None = None
    category: str | None = None
    photos: list[Photo] = field(default_factory=list)
    reviews: list[Review] = field(default_factory=list)
    fetched_at: datetime | None = None
    summary: str | None = None
