"""Pure presentation/formatting helpers for a Place's opening hours and popular-times curve.

Two consumers: the LLM ranker (prompt_context — feeds distance/open-now/busyness into the
match prompt so the model can honour "quán gần", "còn mở", "tránh giờ đông") and the result
card (hours_line / busy_line). Kept free of I/O so both paths share one source of truth.

All "now" reasoning is in Vietnam local time (the app is Hanoi-only) regardless of server TZ.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from backend.domain.entities.place import Place

_VN_TZ = timezone(timedelta(hours=7))
_WEEKDAYS_EN = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
_TIME_TOKEN_RE = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*([AP]M)", re.I)


def _now_vn() -> datetime:
    return datetime.now(_VN_TZ)


def _fmt_hour(hour: float) -> str:
    h = int(hour)
    minutes = round((hour - h) * 60)
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


def hours_line(place: Place) -> str | None:
    """Card line: 'Đang mở · 7h–22h' / 'Đã đóng · mở 7h' / 'Mở cả ngày' / 'Hôm nay đóng cửa'."""
    text = _today_hours_text(place)
    if not text:
        return None
    low = text.lower()
    if "24" in low and "hour" in low:
        return "Mở cả ngày (24h)"
    if "closed" in low:
        return "Hôm nay đóng cửa"

    window = _open_window(text)
    if window is None:
        return text  # unparseable but present — show Maps' raw text rather than nothing
    open_h, close_h = window
    now_h = _now_vn().hour + _now_vn().minute / 60.0
    # Close after midnight (e.g. 6 PM to 1 AM) reads as close_h < open_h.
    is_open = open_h <= now_h < close_h if close_h > open_h else (now_h >= open_h or now_h < close_h)
    span = f"{_fmt_hour(open_h)}–{_fmt_hour(close_h)}"
    return f"Đang mở · {span}" if is_open else f"Đã đóng · mở {_fmt_hour(open_h)}"


def _busy_word(pct: int) -> str:
    if pct < 20:
        return "rất vắng"
    if pct < 40:
        return "khá vắng"
    if pct < 60:
        return "vừa phải"
    if pct < 80:
        return "khá đông"
    return "rất đông"


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


def busy_line(place: Place) -> str | None:
    """Card line: 'Đông nhất 15–17h · hiện giờ khá vắng'."""
    curve = _curve(place)
    peak = _peak_range(curve)
    if peak is None:
        return None
    low, high = peak
    span = f"{low}h" if low == high else f"{low}–{high}h"
    now_pct = curve.get(_now_vn().hour)
    if now_pct is None:
        return f"Đông nhất {span}"
    return f"Đông nhất {span} · hiện giờ {_busy_word(now_pct)}"


def prompt_context(place: Place, distance_m: float | None) -> str:
    """Extra factual lines appended to the LLM match prompt so it can reason about proximity,
    whether the place is open right now, and how busy it tends to be. Only includes what's known."""
    lines: list[str] = []
    if distance_m is not None:
        lines.append(f"- Cách khách khoảng {distance_m / 1000:.1f} km.")

    hours = hours_line(place)
    if hours:
        lines.append(f"- Giờ mở cửa hôm nay: {hours}.")

    busy = busy_line(place)
    if busy:
        lines.append(f"- Mức độ đông khách: {busy}.")

    if not lines:
        return ""
    return "Thông tin thêm về quán:\n" + "\n".join(lines)
