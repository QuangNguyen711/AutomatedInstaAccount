from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.domain.entities.place import Photo, Place, Review
from backend.domain.ports.place_repository import PlaceRepository
from backend.infrastructure.database.models import PhotoModel, PlaceModel, ReviewModel


class SqlAlchemyPlaceRepository(PlaceRepository):
    def __init__(self, session_factory: Callable[[], AsyncSession]):
        self._session_factory = session_factory

    async def find_by_id(self, place_id: str, ttl_days: int) -> Place | None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=ttl_days)

        async with self._session_factory() as session:
            stmt = (
                select(PlaceModel)
                .where(PlaceModel.place_id == place_id)
                .where(PlaceModel.fetched_at >= cutoff)
                .options(selectinload(PlaceModel.photos), selectinload(PlaceModel.reviews))
            )
            row = (await session.execute(stmt)).scalar_one_or_none()

        return self._to_entity(row) if row is not None else None

    async def upsert(self, places: list[Place]) -> None:
        async with self._session_factory() as session:
            for place in places:
                # Must eager-load photos/reviews here: reassigning those relationships below
                # needs their *current* contents first (to orphan/delete the old rows), and an
                # AsyncSession can't do that via an implicit lazy-load outside an awaited call
                # (raises MissingGreenlet) — only matters when `place` already has a row (a
                # re-crawl past its TTL), which a brand-new insert never triggers.
                existing = await session.get(
                    PlaceModel,
                    place.place_id,
                    options=[selectinload(PlaceModel.photos), selectinload(PlaceModel.reviews)],
                )
                if existing is None:
                    existing = PlaceModel(place_id=place.place_id)
                    session.add(existing)

                existing.name = place.name
                existing.address = place.address
                existing.lat = place.lat
                existing.lng = place.lng
                existing.maps_url = place.maps_url
                existing.rating = place.rating
                existing.review_count = place.review_count
                existing.category = place.category
                existing.summary = place.summary
                existing.fetched_at = datetime.now(timezone.utc)

                existing.photos = [
                    PhotoModel(url=p.url, is_good=p.is_good) for p in place.photos
                ]
                existing.reviews = [
                    ReviewModel(
                        text=r.text,
                        author=r.author,
                        rating=r.rating,
                        posted_at=r.posted_at,
                        embedding=r.embedding,
                    )
                    for r in place.reviews
                ]

            await session.commit()

    async def delete(self, place_ids: list[str]) -> None:
        if not place_ids:
            return
        async with self._session_factory() as session:
            await session.execute(delete(PlaceModel).where(PlaceModel.place_id.in_(place_ids)))
            await session.commit()

    @staticmethod
    def _to_entity(row: PlaceModel) -> Place:
        return Place(
            place_id=row.place_id,
            name=row.name,
            address=row.address,
            lat=row.lat,
            lng=row.lng,
            maps_url=row.maps_url,
            rating=row.rating,
            review_count=row.review_count,
            category=row.category,
            summary=row.summary,
            photos=[Photo(url=p.url, is_good=p.is_good) for p in row.photos],
            reviews=[
                Review(
                    text=r.text,
                    author=r.author,
                    rating=r.rating,
                    posted_at=r.posted_at,
                    embedding=list(r.embedding) if r.embedding is not None else None,
                )
                for r in row.reviews
            ],
            fetched_at=row.fetched_at,
        )
