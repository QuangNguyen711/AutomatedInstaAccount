from __future__ import annotations

from backend.domain.ports.llm_provider import LLMProvider


class QueryRewriteService:
    """Simplifies the client's free-text request into a short term Google Maps' own search box
    can actually match on (place category/name), before it's used to build the crawl URL.

    Google Maps search doesn't understand detailed requirements like "must have dark chocolate
    cake" or "quiet atmosphere" — those get evaluated later, against real reviews, by
    RankingService/SummaryService using the client's full original query text. This service only
    narrows down what's sent to Maps itself.
    """

    def __init__(self, llm_provider: LLMProvider):
        self._llm_provider = llm_provider

    async def simplify_for_maps(self, query_text: str) -> str:
        query_text = (query_text or "").strip()
        if not query_text:
            return ""

        prompt = (
            "Chuyển yêu cầu tìm quán ăn/uống dưới đây thành một cụm từ tìm kiếm NGẮN GỌN trên "
            "Google Maps — chỉ nêu loại quán/loại món chính, bỏ hết các yêu cầu chi tiết (nguyên "
            "liệu cụ thể, không gian, giá cả, dịch vụ...), vì Google Maps chỉ tìm được theo loại "
            "hình quán chứ không tìm theo yêu cầu chi tiết.\n"
            'Ví dụ: "quán bánh bắt buộc phải có bánh socola đậm" -> quán bánh ngọt\n'
            'Ví dụ: "cafe yên tĩnh có trà sữa trân châu" -> quán cafe trà sữa\n'
            # English-mode users type in English, but the places are in Hanoi and named/tagged
            # in Vietnamese on Maps — so the search term is always Vietnamese.
            "Yêu cầu có thể viết bằng tiếng Anh — cụm từ tìm kiếm LUÔN trả về bằng tiếng Việt.\n"
            'Ví dụ: "a quiet cafe with good matcha latte" -> quán cafe matcha\n'
            'Ví dụ: "cheap pho place open late" -> quán phở\n\n'
            f'Yêu cầu gốc: "{query_text}"\n\n'
            "Chỉ trả về đúng cụm từ tìm kiếm, không thêm gì khác:"
        )

        try:
            raw = await self._llm_provider.generate(prompt)
        except Exception:
            # A rewrite failure shouldn't block the search — fall back to the raw query text,
            # same as what Maps search used before this feature existed.
            return query_text

        simplified = raw.strip().strip('"').strip("'").strip()
        return simplified or query_text
