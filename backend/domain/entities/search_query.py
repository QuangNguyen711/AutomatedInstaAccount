from __future__ import annotations

from dataclasses import dataclass

# UI + LLM output languages. "vi" is the default (the app is Hanoi-first).
SUPPORTED_LANGS = ("vi", "en")
DEFAULT_LANG = "vi"


def normalize_lang(value: str | None) -> str:
    return value if value in SUPPORTED_LANGS else DEFAULT_LANG


@dataclass
class SearchQuery:
    lat: float
    lng: float
    radius_m: int
    query_text: str
    lang: str = DEFAULT_LANG
