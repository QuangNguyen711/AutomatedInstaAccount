from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.templating import Jinja2Templates

from backend.api.dependencies import get_geocoding_provider, get_search_service
from backend.application.services.search_service import SearchService
from backend.config import get_settings
from backend.domain.entities.search_query import SearchQuery
from backend.domain.ports.geocoding_provider import GeocodingProvider

router = APIRouter(prefix="/api")
templates = Jinja2Templates(directory="backend/api/templates")


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
