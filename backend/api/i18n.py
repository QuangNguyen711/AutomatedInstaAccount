"""UI strings for the two supported languages. The chosen language lives in a `lang` cookie
(set via `/?lang=en`), is passed to the search endpoints as a query param, and flows down to
SearchQuery.lang so the LLM summaries and the hours/busyness lines match the UI.
"""
from __future__ import annotations

from fastapi import Request

from backend.domain.entities.search_query import normalize_lang

LANG_COOKIE = "lang"

_STRINGS: dict[str, dict[str, str]] = {
    "vi": {
        "eyebrow": "Ăn gì · Ở đâu · Gần bạn",
        "tagline": "Tả kiểu quán bạn thèm — tụi mình lục Google Maps, đọc review thật rồi xếp hạng cho.",
        "geo_denied": (
            "Trình duyệt không lấy được vị trí tự động (thường do đang truy cập qua HTTP, không "
            "phải HTTPS) — nhập địa chỉ, mã Plus Code (vd. 3W23+962 Việt Hưng, Hà Nội), hoặc "
            "toạ độ copy từ Google Maps vào ô bên dưới."
        ),
        "label_query": "Thèm gì",
        "placeholder_query": "vd. quán cafe yên tĩnh có trà sữa trân châu",
        "label_location": "Vị trí",
        "placeholder_location": "Địa chỉ / Plus Code / toạ độ",
        "label_radius": "Bán kính",
        "btn_locating": "ĐANG LẤY VỊ TRÍ...",
        "btn_searching": "ĐANG TÌM...",
        "btn_search": "TÌM QUÁN",
        "status_searching": "Đang tìm quán (có thể mất một lúc)...",
        "status_found": "Đã thấy {count} quán, đang tìm thêm...",
        "err_need_location": "Cần vị trí hoặc nhập địa chỉ để tìm.",
        "err_address_not_found": "Không tìm thấy địa chỉ này.",
        "err_geocode_failed": "Không tra được địa chỉ, thử lại sau.",
        "err_search_failed": "Tìm kiếm thất bại, thử lại.",
        "err_connection_lost": "Mất kết nối tới máy chủ, thử lại.",
        "no_results": "Không tìm thấy quán nào phù hợp.",
        "no_address": "Chưa rõ địa chỉ",
        "distance": "Cách {km} km",
        "view_on_maps": "Xem trên Maps →",
        "why_match": "Vì sao hợp",
    },
    "en": {
        "eyebrow": "What · Where · Near you",
        "tagline": "Describe the place you're craving — we dig through Google Maps, read the real reviews and rank them for you.",
        "geo_denied": (
            "Your browser couldn't get your location automatically (usually because the site is "
            "served over HTTP, not HTTPS) — type an address, a Plus Code (e.g. 3W23+962 Việt "
            "Hưng, Hà Nội), or coordinates copied from Google Maps below."
        ),
        "label_query": "Craving",
        "placeholder_query": "e.g. a quiet cafe with bubble milk tea",
        "label_location": "Location",
        "placeholder_location": "Address / Plus Code / coordinates",
        "label_radius": "Radius",
        "btn_locating": "GETTING LOCATION...",
        "btn_searching": "SEARCHING...",
        "btn_search": "FIND PLACES",
        "status_searching": "Searching for places (this can take a while)...",
        "status_found": "Found {count} places, looking for more...",
        "err_need_location": "A location or an address is needed to search.",
        "err_address_not_found": "Couldn't find that address.",
        "err_geocode_failed": "Couldn't look up that address, try again later.",
        "err_search_failed": "Search failed, please try again.",
        "err_connection_lost": "Lost connection to the server, please try again.",
        "no_results": "No matching places found.",
        "no_address": "Address unknown",
        "distance": "{km} km away",
        "view_on_maps": "View on Maps →",
        "why_match": "Why it fits",
    },
}


def strings(lang: str) -> dict[str, str]:
    return _STRINGS[normalize_lang(lang)]


def request_lang(request: Request) -> str:
    """`?lang=` wins (that's how the toggle switches), then the cookie, then the default."""
    return normalize_lang(request.query_params.get("lang") or request.cookies.get(LANG_COOKIE))
