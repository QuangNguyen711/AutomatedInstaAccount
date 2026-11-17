"""Pure presentation/formatting helpers for a Place's opening hours and popular-times curve.

Two consumers: the LLM ranker (prompt_context — feeds distance/open-now/busyness into the
match prompt so the model can honour "quán gần", "còn mở", "tránh giờ đông") and the result
card (hours_line / busy_line). Kept free of I/O so both paths share one source of truth.

All "now" reasoning is in Vietnam local time (the app is Hanoi-only) regardless of server TZ.
Every helper takes a `lang` ("vi" / "en") so card lines and prompt context match the UI language.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from backend.domain.entities.place import Place
from backend.domain.entities.search_query import DEFAULT_LANG, normalize_lang

_VN_TZ = timezone(timedelta(hours=7))
_WEEKDAYS_EN = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
_TIME_TOKEN_RE = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*([AP]M)", re.I)

_TEXT = {
    "vi": {
        "all_day": "Mở cả ngày (24h)",
        "closed_today": "Hôm nay đóng cửa",
        "open_now": "Đang mở · {span}",
        "closed_now": "Đã đóng · mở {open}",
        "peak": "Đông nhất {span}",
        "peak_now": "Đông nhất {span} · hiện giờ {level}",
        "busy_levels": ("rất vắng", "khá vắng", "vừa phải", "khá đông", "rất đông"),
        "ctx_header": "Thông tin thêm về quán:",
        "ctx_distance": "- Cách khách khoảng {km:.1f} km.",
        "ctx_hours": "- Giờ mở cửa hôm nay: {hours}.",
        "ctx_busy": "- Mức độ đông khách: {busy}.",
    },
    "en": {
        "all_day": "Open 24 hours",
        "closed_today": "Closed today",
        "open_now": "Open now · {span}",
        "closed_now": "Closed · opens {open}",
        "peak": "Busiest {span}",
        "peak_now": "Busiest {span} · {level} right now",
        "busy_levels": ("very quiet", "fairly quiet", "moderate", "fairly busy", "very busy"),
        "ctx_header": "Extra info about the place:",
        "ctx_distance": "- About {km:.1f} km from the customer.",
        "ctx_hours": "- Opening hours today: {hours}.",
        "ctx_busy": "- How busy it gets: {busy}.",
    },
}


def _t(lang: str) -> dict:
    return _TEXT[normalize_lang(lang)]


def _now_vn() -> datetime:
    return datetime.now(_VN_TZ)


def _fmt_hour(hour: float, lang: str = DEFAULT_LANG) -> str:
    h = int(hour)
    minutes = round((hour - h) * 60)
    if normalize_lang(lang) == "en":
        return f"{h}:{minutes:02d}"
    return f"{h}h{minutes:02d}" if minutes else f"{h}h"


def _token_to_hour(token_match: re.Match) -> float:
    hour = int(token_match.group(1)) % 12
    minutes = int(token_match.group(2)) if token_match.group(2) else 0
    if token_match.group(3).upper() == "PM":
        hour += 12
    return hour + minutes / 60.0


def _today_hours_text(place: Place) -> str | None:
    if not place.opening_hours:
        return None
    today = _WEEKDAYS_EN[_now_vn().weekday()]
    return place.opening_hours.get(today)


def _open_window(hours_text: str) -> tuple[float, float] | None:
    """First open time + last close time of the day, as 24h floats. Split hours collapse to the
    outer window (good enough for an "open now / until when" line)."""
    tokens = list(_TIME_TOKEN_RE.finditer(hours_text))
    if len(tokens) < 2:
        return None
    return _token_to_hour(tokens[0]), _token_to_hour(tokens[-1])


def hours_line(place: Place, lang: str = DEFAULT_LANG) -> str | None:
    """Card line: 'Đang mở · 7h–22h' / 'Đã đóng · mở 7h' / 'Mở cả ngày' / 'Hôm nay đóng cửa'
    (or the English equivalents)."""
    t = _t(lang)
    text = _today_hours_text(place)
    if not text:
        return None
    low = text.lower()
    if "24" in low and "hour" in low:
        return t["all_day"]
    if "closed" in low:
        return t["closed_today"]

    window = _open_window(text)
    if window is None:
        return text  # unparseable but present — show Maps' raw text rather than nothing
    open_h, close_h = window
    now_h = _now_vn().hour + _now_vn().minute / 60.0
    # Close after midnight (e.g. 6 PM to 1 AM) reads as close_h < open_h.
    is_open = open_h <= now_h < close_h if close_h > open_h else (now_h >= open_h or now_h < close_h)
    span = f"{_fmt_hour(open_h, lang)}–{_fmt_hour(close_h, lang)}"
    if is_open:
        return t["open_now"].format(span=span)
    return t["closed_now"].format(open=_fmt_hour(open_h, lang))


def _busy_word(pct: int, lang: str = DEFAULT_LANG) -> str:
    levels = _t(lang)["busy_levels"]
    for i, upper in enumerate((20, 40, 60, 80)):
        if pct < upper:
            return levels[i]
    return levels[-1]


def _peak_range(curve: dict[int, int]) -> tuple[int, int] | None:
    if not curve:
        return None
    peak = max(curve.values())
    if peak <= 0:
        return None
    threshold = max(70, int(peak * 0.85))
    peak_hours = sorted(h for h, pct in curve.items() if pct >= threshold)
    return (peak_hours[0], peak_hours[-1]) if peak_hours else None


def _curve(place: Place) -> dict[int, int]:
    if not place.popular_times:
        return {}
    return {int(h): int(pct) for h, pct in place.popular_times.items()}


def busy_line(place: Place, lang: str = DEFAULT_LANG) -> str | None:
    """Card line: 'Đông nhất 15–17h · hiện giờ khá vắng' / 'Busiest 15:00–17:00 · fairly quiet right now'."""
    t = _t(lang)
    curve = _curve(place)
    peak = _peak_range(curve)
    if peak is None:
        return None
    low, high = peak
    if normalize_lang(lang) == "en":
        span = _fmt_hour(low, lang) if low == high else f"{_fmt_hour(low, lang)}–{_fmt_hour(high, lang)}"
    else:
        span = f"{low}h" if low == high else f"{low}–{high}h"
    now_pct = curve.get(_now_vn().hour)
    if now_pct is None:
        return t["peak"].format(span=span)
    return t["peak_now"].format(span=span, level=_busy_word(now_pct, lang))


def prompt_context(place: Place, distance_m: float | None, lang: str = DEFAULT_LANG) -> str:
    """Extra factual lines appended to the LLM match prompt so it can reason about proximity,
    whether the place is open right now, and how busy it tends to be. Only includes what's known."""
    t = _t(lang)
    lines: list[str] = []
    if distance_m is not None:
        lines.append(t["ctx_distance"].format(km=distance_m / 1000))

    hours = hours_line(place, lang)
    if hours:
        lines.append(t["ctx_hours"].format(hours=hours))

    busy = busy_line(place, lang)
    if busy:
        lines.append(t["ctx_busy"].format(busy=busy))

    if not lines:
        return ""
    return t["ctx_header"] + "\n" + "\n".join(lines)
