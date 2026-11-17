from __future__ import annotations

import os

from backend.application.services.query_rewrite_service import QueryRewriteService
from backend.application.services.ranking_service import RankingService
from backend.application.services.search_service import SearchService
from backend.application.services.summary_service import SummaryService
from backend.config import get_settings
from backend.domain.ports.llm_provider import LLMProvider
from backend.infrastructure.database.repositories.place_repository import (
    SqlAlchemyPlaceRepository,
)
from backend.infrastructure.database.session import SessionLocal
from backend.infrastructure.geocoding.photon_geocoding_provider import (
    PhotonGeocodingProvider,
)
from backend.infrastructure.llm.noop_llm_provider import NoOpLLMProvider
from backend.infrastructure.llm.nvidia_llm_provider import NvidiaLLMProvider
from backend.infrastructure.places.playwright_places_provider import PlaywrightPlacesProvider
from backend.infrastructure.vision.yolo_classifier_provider import YoloClassifierProvider

# Singletons, built once at process start — same pattern as SlideGen's api/dependencies.py
_settings = get_settings()

_auth_state_path = _settings.google_auth_state_path
if _auth_state_path and not os.path.exists(_auth_state_path):
    _auth_state_path = None  # fall back to a logged-out session rather than erroring

_places_provider = PlaywrightPlacesProvider(
    max_results=_settings.max_crawl_results,
    storage_state_path=_auth_state_path,
)
_image_classifier = YoloClassifierProvider(weights_path=_settings.yolo_weights_path)
_place_repository = SqlAlchemyPlaceRepository(SessionLocal)
_geocoding_provider = PhotonGeocodingProvider()

_llm_provider: LLMProvider
if _settings.llm_enabled and _settings.llm_api_url and _settings.llm_api_key:
    _llm_provider = NvidiaLLMProvider(
        api_url=_settings.llm_api_url,
        api_key=_settings.llm_api_key,
        model_name=_settings.llm_model_name,
        reasoning_enabled=_settings.llm_reasoning_enabled,
    )
else:
    _llm_provider = NoOpLLMProvider()

_summary_service = SummaryService(llm_provider=_llm_provider)
_ranking_service = RankingService(summary_service=_summary_service, settings=_settings)
_query_rewrite_service = QueryRewriteService(llm_provider=_llm_provider)

_search_service = SearchService(
    places_provider=_places_provider,
    place_repository=_place_repository,
    image_classifier=_image_classifier,
    ranking_service=_ranking_service,
    query_rewrite_service=_query_rewrite_service,
    settings=_settings,
)


def get_search_service() -> SearchService:
    return _search_service


def get_geocoding_provider() -> PhotonGeocodingProvider:
    return _geocoding_provider
