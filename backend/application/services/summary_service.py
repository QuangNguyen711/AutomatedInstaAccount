from __future__ import annotations

import re
from datetime import datetime, timezone

from backend.domain.entities.place import Place, Review
from backend.domain.ports.llm_provider import LLMProvider

_MAX_REVIEWS_IN_PROMPT = 10
_SCORE_RE = re.compile(r"SCORE:\s*([\d.]+)", re.I)
_SUMMARY_RE = re.compile(r"SUMMARY:\s*(.+)", re.I | re.S)


def _recency_label(posted_at: datetime | None) -> str:
    if posted_at is None:
        return "không rõ thời điểm"
    days = (datetime.now(timezone.utc) - posted_at).days
    if days < 30:
        return f"{max(days, 1)} ngày trước"
    if days < 365:
        return f"{days // 30} tháng trước"
    return f"{days // 365} năm trước"


def _format_review(review: Review) -> str:
    rating = f"{review.rating} sao" if review.rating is not None else "chưa rõ số sao"
    return f"- [{rating}, {_recency_label(review.posted_at)}] {review.text}"


class SummaryService:
    """Scores how well a place matches the client's free-text request and writes a one-line
    reason, in a single LLM call — query-aware, so it must run per search (not cached at
    ingest time like a place-level fact would be).
    """

    def __init__(self, llm_provider: LLMProvider):
        self._llm_provider = llm_provider

    async def generate_query_match(
        self, place: Place, query_text: str
    ) -> tuple[str | None, float]:
        if not place.reviews:
            return None, 0.0

        reviews_sorted = sorted(
            place.reviews,
            key=lambda r: r.posted_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )[:_MAX_REVIEWS_IN_PROMPT]
        reviews_block = "\n".join(_format_review(r) for r in reviews_sorted)

        prompt = (
            f'Đánh giá mức độ phù hợp của quán "{place.name}" với yêu cầu của khách, '
            "dựa trên review thật của quán bên dưới (mới nhất trước — ưu tiên review gần đây "
            "hơn review cũ khi đánh giá).\n\n"
            f'Yêu cầu của khách: "{query_text or "không có yêu cầu cụ thể, chỉ tìm quán gần đây"}"\n\n'
            f"Review:\n{reviews_block}\n\n"
            "Trả lời ĐÚNG theo 2 dòng sau, không thêm gì khác:\n"
            "SCORE: <một số từ 0 đến 10, 10 = rất phù hợp yêu cầu, 0 = không liên quan/không đủ "
            "thông tin để đánh giá>\n"
            "SUMMARY: <một câu NGẮN GỌN, tối đa 25 từ, tiếng Việt, nêu lý do phù hợp hoặc không "
            "phù hợp với yêu cầu>"
        )

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
