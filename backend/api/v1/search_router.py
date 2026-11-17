from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates

from backend.api.dependencies import get_geocoding_provider, get_search_service
from backend.application.services.place_context import busy_line, hours_line
from backend.application.services.search_service import SearchService
from backend.config import get_settings
from backend.domain.entities.search_query import SearchQuery
from backend.domain.ports.geocoding_provider import GeocodingProvider

router = APIRouter(prefix="/api")
templates = Jinja2Templates(directory="backend/api/templates")
# Card presenters — derive the "Đang mở · 7h–22h" / "Đông nhất 15–17h · hiện giờ khá vắng" lines
# from a place's opening_hours / popular_times at render time (they depend on the current VN hour).
templates.env.globals["hours_line"] = hours_line
templates.env.globals["busy_line"] = busy_line


def _sse(event: str, data: str) -> str:
    # SSE frames: an "event:" line, then one "data:" line per line of payload (the card HTML is
    # multi-line), then a blank line to dispatch. See the EventSource wiring in index.html.
    body = "".join(f"data: {line}\n" for line in data.split("\n"))
    return f"event: {event}\n{body}\n"


@router.get("/geocode")
async def geocode(
    address: str,
    geocoding_provider: GeocodingProvider = Depends(get_geocoding_provider),
):
    # Fallback for browsers that refuse navigator.geolocation on a non-HTTPS origin (notably
    # iOS Safari/Chrome over a plain-HTTP LAN address) — lets the client type an address instead.
    result = await geocoding_provider.geocode(address)
    if result is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy địa chỉ này")
    lat, lng = result
    return {"lat": lat, "lng": lng}


@router.post("/search")
async def search(
    request: Request,
    lat: float = Form(...),
    lng: float = Form(...),
    query_text: str = Form(""),
    radius_m: int | None = Form(None),
    search_service: SearchService = Depends(get_search_service),
):
    settings = get_settings()
    query = SearchQuery(
        lat=lat,
        lng=lng,
        radius_m=radius_m or settings.default_search_radius_m,
        query_text=query_text,
    )
    results = await search_service.search(query)
    return templates.TemplateResponse(request, "partials/results.html", {"results": results})


@router.get("/search/stream")
async def search_stream(
    lat: float,
    lng: float,
    query_text: str = "",
    radius_m: int | None = None,
    search_service: SearchService = Depends(get_search_service),
):
    # Streams one SSE "place" event per result as it finishes, then a "done" event carrying the
    # final count. EventSource is GET-only, hence query params (no sensitive data here).
    settings = get_settings()
    query = SearchQuery(
        lat=lat,
        lng=lng,
        radius_m=radius_m or settings.default_search_radius_m,
        query_text=query_text,
    )
    slide_template = templates.get_template("partials/place_slide.html")

    async def event_gen():
        count = 0
        try:
            async for ranked in search_service.search_stream(query):
                count += 1
                yield _sse("place", slide_template.render(r=ranked))
            yield _sse("done", str(count))
        except Exception:
            yield _sse("error", "search failed")

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        # Disable proxy/browser buffering so events flush immediately as they're produced.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
