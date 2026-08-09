from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://placesfinder:placesfinder@localhost:5432/placesfinder"

    cache_ttl_days: int = 14
    default_search_radius_m: int = 3000
    # Keep these two equal: a place beyond max_detail_pages only gets its listing thumbnail
    # (no reviews, no other photos, no summary), so a mismatch produces a mix of fully-enriched
    # and half-empty cards in the same result set. Each detail page costs ~20-40s (headed
    # browser, review + review-photo scraping).
    max_crawl_results: int = 8
    max_detail_pages: int = 8

    # Not currently used for ranking (see RankingService — relevance now comes from a
    # query-aware LLM match score instead of embedding similarity). Left configurable in case
    # embeddings get reintroduced later; infrastructure/embedding/ still has the provider.
    embedding_enabled: bool = False
    embedding_api_url: str | None = None
    embedding_api_key: str | None = None
    embedding_model_name: str = "nvidia/nv-embedqa-e5-v5"

    llm_enabled: bool = False
    llm_api_url: str | None = None
    llm_api_key: str | None = None
    llm_model_name: str = "nvidia/nemotron-3-nano-30b-a3b"
    llm_reasoning_enabled: bool = False

    yolo_weights_path: str = "backend/infrastructure/vision/weights/best_cls.pt"

    # Saved Playwright storage_state from a one-time Google login — see .secrets/ (gitignored).
    # Without it, Maps serves a "limited view" with no reviews to logged-out/automated sessions.
    google_auth_state_path: str | None = ".secrets/google_auth_state.json"

    ranking_weight_relevance: float = 0.6
    ranking_weight_distance: float = 0.4


@lru_cache
def get_settings() -> Settings:
    return Settings()
