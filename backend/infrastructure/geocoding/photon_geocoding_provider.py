from __future__ import annotations

import re

import httpx
from openlocationcode import openlocationcode as olc

from backend.domain.ports.geocoding_provider import GeocodingProvider

_SEARCH_URL = "https://photon.komoot.io/api/"

# Google "Plus Codes" (Open Location Code), e.g. "3W23+962 Việt Hưng, Hà Nội" — the format
# Google Maps itself shows/copies for a pinned location. A SHORT code (no leading area digits,
# the common case when copied off a nearby map view) needs a locality reference to resolve;
# the geocoding API doesn't understand this format at all, so it's decoded locally instead.
_PLUS_CODE_RE = re.compile(
    r"^([23456789CFGHJMPQRVWX]{2,8}\+[23456789CFGHJMPQRVWX]{2,7})(?:\s+(.+))?$", re.I
)


class PhotonGeocodingProvider(GeocodingProvider):
    """Free geocoding via Komoot's Photon (OpenStreetMap data) — no API key.

    Replaces the earlier Nominatim provider: nominatim.openstreetmap.org turned out to be
    blocked at the TLS layer on the deployment network (SSL handshake reset, consistent with
    SNI-based filtering — failed from both the host and the container while other HTTPS hosts
    worked fine). Photon serves the same OSM data from a different domain that isn't blocked.
    """

    def __init__(self, timeout_s: float = 10.0):
        self._client = httpx.AsyncClient(
            headers={"User-Agent": "PlacesFinder/1.0 (personal use)"}, timeout=timeout_s
        )

    async def geocode(self, address: str) -> tuple[float, float] | None:
        address = address.strip()
        plus_code_match = _PLUS_CODE_RE.match(address)
        if plus_code_match:
            result = await self._geocode_plus_code(
                plus_code_match.group(1), plus_code_match.group(2)
            )
            if result is not None:
                return result
        return await self._geocode_address(address)

    async def _geocode_plus_code(
        self, code: str, locality: str | None
    ) -> tuple[float, float] | None:
        code = code.upper()
        if not olc.isValid(code):
            return None
        if olc.isFull(code):
            area = olc.decode(code)
            return area.latitudeCenter, area.longitudeCenter
        if not locality:
            return None
        reference = await self._geocode_address(locality)
        if reference is None:
            return None
        full_code = olc.recoverNearest(code, reference[0], reference[1])
        area = olc.decode(full_code)
        return area.latitudeCenter, area.longitudeCenter

    async def _geocode_address(self, address: str) -> tuple[float, float] | None:
        response = await self._client.get(_SEARCH_URL, params={"q": address, "limit": 1})
        response.raise_for_status()
        features = response.json().get("features", [])
        if not features:
            return None
        # Photon returns GeoJSON: coordinates are [lng, lat], the reverse of Nominatim's lat/lon.
        lng, lat = features[0]["geometry"]["coordinates"]
        return float(lat), float(lng)
