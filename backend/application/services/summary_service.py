from __future__ import annotations

import re
from datetime import datetime, timezone

from backend.application.services.place_context import prompt_context
from backend.domain.entities.place import Place, Review
from backend.domain.entities.search_query import DEFAULT_LANG
from backend.domain.ports.llm_provider import LLMProvider

_MAX_REVIEWS_IN_PROMPT = 10
_SCORE_RE = re.compile(r"SCORE:\s*([\d.]+)", re.I)
_SUMMARY_RE = re.compile(r"SUMMARY:\s*(.+)", re.I | re.S)


def _recency_label(posted_at: datetime | None, lang: str) -> str:
    en = lang == "en"
    if posted_at is None:
        return "date unknown" if en else "không rõ thời điểm"
    days = (datetime.now(timezone.utc) - posted_at).days
    if days < 30:
        return f"{max(days, 1)} days ago" if en else f"{max(days, 1)} ngày trước"
    if days < 365:
        return f"{days // 30} months ago" if en else f"{days // 30} tháng trước"
    return f"{days // 365} years ago" if en else f"{days // 365} năm trước"


def _format_review(review: Review, lang: str) -> str:
    en = lang == "en"
    if review.rating is not None:
        rating = f"{review.rating} stars" if en else f"{review.rating} sao"
    else:
        rating = "rating unknown" if en else "chưa rõ số sao"
    return f"- [{rating}, {_recency_label(review.posted_at, lang)}] {review.text}"


def _build_prompt_vi(name: str, query_text: str, context_section: str, reviews_block: str) -> str:
    return (
        f'Đánh giá mức độ phù hợp của quán "{name}" với yêu cầu của khách, '
        "dựa trên review thật của quán bên dưới (mới nhất trước — ưu tiên review gần đây "
        "hơn review cũ khi đánh giá).\n\n"
        f'Yêu cầu của khách: "{query_text or "không có yêu cầu cụ thể, chỉ tìm quán gần đây"}"\n\n'
        f"{context_section}"
        f"Review:\n{reviews_block}\n\n"
        "Trả lời ĐÚNG theo 2 dòng sau, không thêm gì khác:\n"
        "SCORE: <một số từ 0 đến 10, 10 = rất phù hợp yêu cầu, 0 = không liên quan/không đủ "
        "thông tin để đánh giá>\n"
        "SUMMARY: <một câu NGẮN GỌN, tối đa 25 từ, tiếng Việt, nêu lý do phù hợp hoặc không "
        "phù hợp với yêu cầu>"
    )


def _build_prompt_en(name: str, query_text: str, context_section: str, reviews_block: str) -> str:
    # The reviews themselves stay in whatever language they were written (mostly Vietnamese) —
    # the model reads them as-is but is told to answer in English.
    return (
        f'Rate how well the place "{name}" matches the customer\'s request, based on its real '
        "reviews below (newest first — weigh recent reviews more than older ones). The reviews "
        "may be written in Vietnamese or other languages.\n\n"
        f'Customer request: "{query_text or "no specific request, just looking for a place nearby"}"\n\n'
        f"{context_section}"
        f"Reviews:\n{reviews_block}\n\n"
        "Reply with EXACTLY these 2 lines and nothing else:\n"
        "SCORE: <a number from 0 to 10, 10 = a great match, 0 = unrelated / not enough "
        "information to judge>\n"
        "SUMMARY: <one SHORT sentence, at most 25 words, written in ENGLISH (translate any "
        "Vietnamese details), explaining why it does or doesn't match the request>"
    )


class SummaryService:
    """Scores how well a place matches the client's free-text request and writes a one-line
    reason, in a single LLM call — query-aware, so it must run per search (not cached at
    ingest time like a place-level fact would be). The prompt (and so the summary) follows the
    UI language.
    """

    def __init__(self, llm_provider: LLMProvider):
        self._llm_provider = llm_provider

    async def generate_query_match(
        self,
        place: Place,
        query_text: str,
        distance_m: float | None = None,
        lang: str = DEFAULT_LANG,
    ) -> tuple[str | None, float]:
        if not place.reviews:
            return None, 0.0

        reviews_sorted = sorted(
            place.reviews,
            key=lambda r: r.posted_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )[:_MAX_REVIEWS_IN_PROMPT]
        reviews_block = "\n".join(_format_review(r, lang) for r in reviews_sorted)

        # Distance / open-now / busyness — lets the model honour requests like "quán gần",
        # "giờ này còn mở không", "tránh giờ đông". Empty when none of it is known.
        context_block = prompt_context(place, distance_m, lang)
        context_section = f"{context_block}\n\n" if context_block else ""

        build_prompt = _build_prompt_en if lang == "en" else _build_prompt_vi
        prompt = build_prompt(place.name, query_text, context_section, reviews_block)

        raw = await self._llm_provider.generate(prompt)
        return self._parse(raw)

    @staticmethod
    def _parse(raw: str) -> tuple[str | None, float]:
        score_match = _SCORE_RE.search(raw)
        summary_match = _SUMMARY_RE.search(raw)

        score = 0.0
        if score_match:
            try:
                score = max(0.0, min(10.0, float(score_match.group(1))))
            except ValueError:
                score = 0.0

        summary = summary_match.group(1).strip() if summary_match else raw.strip() or None
        return summary, score
