from __future__ import annotations

import asyncio
import random
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from patchright.async_api import async_playwright

from backend.domain.entities.place import Photo, Place, Review
from backend.domain.entities.search_query import SearchQuery
from backend.domain.ports.places_provider import PlacesProvider

# Google appends accessibility hints to a link's aria-label for links already in browser
# history (e.g. "Kén Coffee Đại Mỗ · Visited link") — happens because searches reuse the same
# signed-in browser profile/session repeatedly. Strip it so it doesn't leak into the place name.
_ARIA_SUFFIX_RE = re.compile(r"\s*[·\-]\s*Visited link\s*$", re.I)
_RATING_RE = re.compile(r"([\d.]+)\s*star", re.I)
_REVIEW_COUNT_RE = re.compile(r"([\d,]+)\s*review", re.I)
_COORDS_RE = re.compile(r"!3d(-?[\d.]+)!4d(-?[\d.]+)")
_PLACE_ID_RE = re.compile(r"!1s([^!]+)")
_RELATIVE_TIME_RE = re.compile(r"\b(a|an|\d+)\s+(day|week|month|year)s?\s+ago\b", re.I)
_RELATIVE_TIME_DAYS = {"day": 1, "week": 7, "month": 30, "year": 365}
_STABLE_SCROLL_ROUNDS = 3
_SCROLL_PAUSE_RANGE = (0.8, 2.0)
_REVIEWS_TAB_RETRY_ATTEMPTS = 4
_REVIEWS_TAB_RETRY_PAUSE_S = 1.0
_REVIEWS_LOAD_MORE_SCROLLS = 4
_MAX_REVIEWS_PER_PLACE = 20
# Google's photo CDN URLs encode the served resolution in a "=w{width}-h{height}..." suffix —
# the thumbnails in listing cards and the Overview preview strip are small (seen as low as
# 32x32), and stretching those to fill a card's photo grid is exactly what was reading as
# "blurry". Requesting a larger size through the same URL avoids re-fetching anything extra.
_PHOTO_SIZE_RE = re.compile(r"=w\d+-h\d+[^=]*$")
_PHOTO_UPSCALE_SUFFIX = "=w800-h800-k-no"


def _upscale_photo_url(url: str) -> str:
    if not url:
        return url
    if _PHOTO_SIZE_RE.search(url):
        return _PHOTO_SIZE_RE.sub(_PHOTO_UPSCALE_SUFFIX, url)
    return url

# Finds the actual scrollable detail-pane div (Google's class names for it churn/are obfuscated,
# but "the scrollable element with the biggest scrollHeight-clientHeight gap" is stable). Scrolling
# this pane is what triggers the Overview/Reviews/About tab bar to render at all — without it,
# get_by_role("tab") finds nothing even after networkidle.
_FIND_SCROLLABLE_PANE_JS = """
() => {
    const all = document.querySelectorAll('*');
    let best = null, bestScore = 0;
    for (const el of all) {
        const style = getComputedStyle(el);
        const scrollable = (style.overflowY === 'auto' || style.overflowY === 'scroll');
        if (scrollable && el.scrollHeight > el.clientHeight) {
            const score = el.scrollHeight - el.clientHeight;
            if (score > bestScore) { bestScore = score; best = el; }
        }
    }
    if (!best) return false;
    best.setAttribute('data-scrollpane', 'true');
    return true;
}
"""

_MAX_REVIEW_PHOTOS_PER_PLACE = 20

# Extracts photos attached to individual reviews. These render as a CSS background-image on
# <button class="Tya61d"> — no <img> tag, no ARIA role — found by scanning computed styles for
# any element whose background-image points at Google's user-photo CDN.
_SCAN_REVIEW_PHOTOS_JS = """
() => {
    const all = document.querySelectorAll('*');
    const urls = [];
    for (const el of all) {
        const bg = getComputedStyle(el).backgroundImage;
        if (bg && bg.includes('googleusercontent')) {
            const match = bg.match(/url\\("?(.*?)"?\\)/);
            if (match) urls.push(match[1]);
        }
    }
    return urls;
}
"""


def _parse_relative_time(text: str) -> datetime | None:
    match = _RELATIVE_TIME_RE.search(text)
    if not match:
        return None
    count = 1 if match.group(1).lower() in ("a", "an") else int(match.group(1))
    days = count * _RELATIVE_TIME_DAYS[match.group(2).lower()]
    return datetime.now(timezone.utc) - timedelta(days=days)


class PlaywrightPlacesProvider(PlacesProvider):
    """Scrapes Google Maps search results with Playwright/Patchright.

    NOTE: relies on Google Maps' ARIA roles (feed/article/tab) rather than its obfuscated
    CSS class names where possible, since the latter churn frequently. A couple of spots
    (review text nodes, the scrollable detail pane) still fall back to a structural/JS
    guess and are the most likely things to need live tuning against the current markup.

    Requires a signed-in session (storage_state_path) to get reviews at all — logged-out
    requests get Google's stripped-down "limited view" of Maps with no review data.
    """

    def __init__(
        self,
        max_results: int = 40,
        storage_state_path: str | None = None,
    ):
        self._max_results = max_results
        # Without a signed-in session, Google serves a "limited view" of Maps (no reviews,
        # restricted photos) to automated-looking browsers. storage_state_path points at cookies
        # saved from a one-time login (see scripts/ — not committed, .secrets/ is gitignored).
        # The account's own language preference must be English for the ARIA-text matching
        # throughout this file to work (Maps UI language follows account settings once signed
        # in, overriding the context `locale` below).
        self._storage_state_path = storage_state_path

    async def search_listings(self, query: SearchQuery) -> list[Place]:
        search_url = self._build_search_url(query)

        async with async_playwright() as pw:
            # NOTE: must run non-headless — confirmed live that Google Maps' Overview/Reviews/
            # About tab bar simply never renders in headless mode (even "new" headless), with
            # or without a signed-in session, while headed mode renders it reliably. In Docker
            # (no real display) this requires Xvfb — see Dockerfile (`xvfb-run` wraps uvicorn).
            browser = await pw.chromium.launch(headless=False)
            context = await browser.new_context(
                locale="en-US", storage_state=self._storage_state_path
            )
            page = await context.new_page()
            await page.goto(search_url, wait_until="domcontentloaded")

            listings = await self._scrape_listings(page)
            places = self._to_places(listings)

            await context.close()
            await browser.close()

        return places

    async def fetch_details(self, places: list[Place]) -> None:
        if not places:
            return

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=False)
            context = await browser.new_context(
                locale="en-US", storage_state=self._storage_state_path
            )

            for place in places:
                await self._enrich_with_details(context, place)
                await asyncio.sleep(random.uniform(*_SCROLL_PAUSE_RANGE))

            await context.close()
            await browser.close()

    @staticmethod
    def _build_search_url(query: SearchQuery) -> str:
        term = quote(query.query_text or "quan an quan cafe")
        return f"https://www.google.com/maps/search/{term}/@{query.lat},{query.lng},15z"

    async def _scrape_listings(self, page) -> list[dict]:
        feed = page.get_by_role("feed")
        try:
            await feed.wait_for(timeout=15_000)
        except Exception:
            return []

        stable_rounds = 0
        last_count = 0
        while stable_rounds < _STABLE_SCROLL_ROUNDS:
            count = await page.get_by_role("article").count()
            if count >= self._max_results:
                break
            stable_rounds = stable_rounds + 1 if count == last_count else 0
            last_count = count

            await feed.evaluate("el => el.scrollTo(0, el.scrollHeight)")
            await asyncio.sleep(random.uniform(*_SCROLL_PAUSE_RANGE))

        cards = await page.get_by_role("article").all()
        listings = [await self._extract_card(card) for card in cards[: self._max_results]]
        return [item for item in listings if item]

    @staticmethod
    async def _extract_card(card) -> dict | None:
        # The article div itself carries no aria-label — the accessible name lives on the
        # nested <a class="hfpxzc"> anchor, which also happens to embed lat/lng in its href.
        anchor = card.locator("a").first
        if not await anchor.count():
            return None

        name = await anchor.get_attribute("aria-label")
        href = await anchor.get_attribute("href")
        if not name or not href:
            return None
        name = _ARIA_SUFFIX_RE.sub("", name).strip()

        img = card.locator("img").first
        thumbnail = await img.get_attribute("src") if await img.count() else None

        rating, review_count = None, None
        rating_el = card.get_by_role("img", name=re.compile(r"star", re.I)).first
        if await rating_el.count():
            label = await rating_el.get_attribute("aria-label") or ""
            rating_match = _RATING_RE.search(label)
            count_match = _REVIEW_COUNT_RE.search(label)
            if rating_match:
                rating = float(rating_match.group(1))
            if count_match:
                review_count = int(count_match.group(1).replace(",", ""))

        return {
            "name": name,
            "maps_url": href or "",
            "thumbnail": thumbnail,
            "rating": rating,
            "review_count": review_count,
        }

    def _to_places(self, listings: list[dict]) -> list[Place]:
        places = []
        for item in listings:
            if not item["maps_url"]:
                continue
            coords = _COORDS_RE.search(item["maps_url"])
            lat, lng = (float(coords.group(1)), float(coords.group(2))) if coords else (0.0, 0.0)
            places.append(
                Place(
                    place_id=self._place_id_from_url(item["maps_url"]),
                    name=item["name"],
                    address="",
                    lat=lat,
                    lng=lng,
                    maps_url=item["maps_url"],
                    rating=item["rating"],
                    review_count=item["review_count"],
                    photos=(
                        [Photo(url=_upscale_photo_url(item["thumbnail"]))]
                        if item["thumbnail"]
                        else []
                    ),
                )
            )
        return places

    @staticmethod
    def _place_id_from_url(url: str) -> str:
        match = _PLACE_ID_RE.search(url)
        return match.group(1) if match else url

    async def _enrich_with_details(self, context, place: Place) -> None:
        page = await context.new_page()
        try:
            await page.goto(place.maps_url, wait_until="domcontentloaded", timeout=20_000)
            try:
                await page.wait_for_load_state("networkidle", timeout=15_000)
            except Exception:
                pass  # detail pane sometimes keeps a background XHR open; don't block on it
            await page.wait_for_timeout(1500)

            address_btn = page.get_by_role("button", name=re.compile(r"^address", re.I)).first
            if await address_btn.count():
                label = await address_btn.get_attribute("aria-label") or ""
                place.address = re.sub(r"^address:\s*", "", label, flags=re.I).strip()

            coords = _COORDS_RE.search(page.url)
            if coords:
                place.lat, place.lng = float(coords.group(1)), float(coords.group(2))

            # Scroll the detail pane once — this both loads more of the Overview photo strip
            # and is required for the Overview/Reviews/About tab bar to render at all (found
            # live by inspection, not documented anywhere). Class names are obfuscated, so the
            # scrollable container is found by JS (biggest scrollHeight-clientHeight gap) rather
            # than a selector.
            try:
                has_pane = await page.evaluate(_FIND_SCROLLABLE_PANE_JS)
            except Exception:
                has_pane = False
            pane = page.locator('[data-scrollpane="true"]').first if has_pane else page
            if has_pane:
                for _ in range(5):
                    await pane.evaluate("el => el.scrollBy(0, 800)")
                    await page.wait_for_timeout(500)

            # Photos: scrape from Overview *before* switching to the Reviews tab below, which
            # replaces the pane's content — scraping after the switch was silently picking up
            # whatever the Reviews tab happened to show instead. Filtered to the "/gps-cs-s/"
            # path Google uses for venue photos: an unfiltered query also matches reviewer
            # avatar thumbnails ("/a/", "/a-/" paths), which flooded the grid with headshots.
            for img in await page.locator("img[src*='googleusercontent']").all():
                src = await img.get_attribute("src")
                if src and "/gps-cs-s/" in src:
                    upscaled = _upscale_photo_url(src)
                    if not any(p.url == upscaled for p in place.photos):
                        place.photos.append(Photo(url=upscaled))

            await self._scrape_reviews(page, place)
        except Exception:
            # detail scraping is best-effort — keep the listing-level data we already have
            pass
        finally:
            await page.close()

    @staticmethod
    async def _scrape_reviews(page, place: Place) -> None:
        # Match by text, not fixed position — tab order isn't always Overview/Reviews/About;
        # places with a menu get Overview/Menu/Reviews/About instead, confirmed live. Text
        # matching only works because the signed-in account's language is forced to English
        # (see google_auth_state setup) — Maps' UI otherwise follows the account's language.
        reviews_tab = page.get_by_role("tab", name=re.compile(r"^reviews", re.I)).first
        found = False
        for _ in range(_REVIEWS_TAB_RETRY_ATTEMPTS):
            if await reviews_tab.count():
                found = True
                break
            await page.wait_for_timeout(int(_REVIEWS_TAB_RETRY_PAUSE_S * 1000))
        if not found:
            return

        await reviews_tab.click()
        await page.wait_for_timeout(1500)

        # Reviews lazy-load ~10 at a time as the pane scrolls — re-find the scrollable
        # container (the Reviews tab swaps the pane's content, so the earlier Overview-tab
        # reference may be stale) and nudge it to pull in more before extracting.
        try:
            has_pane = await page.evaluate(_FIND_SCROLLABLE_PANE_JS)
        except Exception:
            has_pane = False
        if has_pane:
            reviews_pane = page.locator('[data-scrollpane="true"]').first
            for _ in range(_REVIEWS_LOAD_MORE_SCROLLS):
                await reviews_pane.evaluate("el => el.scrollBy(0, 1000)")
                await page.wait_for_timeout(600)

        # Review cards carry no ARIA role at all (confirmed by walking the DOM live — role is
        # None all the way up from the star-rating element to the card root), unlike the
        # role="article" place cards on the search-results feed. `.jftiEf` is Google's actual
        # class name for the review card wrapper — brittle (obfuscated, can churn), but it's
        # the only hook available; verified against real cards (10 matched a page showing 10
        # loaded reviews) rather than guessed.
        for review_card in (await page.locator(".jftiEf").all())[:_MAX_REVIEWS_PER_PLACE]:
            # inner_text() includes author/metadata noise alongside the review body — accepted
            # for now, refine extraction to just the body paragraph once live-verified (this
            # affects embedding/summary quality but not correctness of rating/posted_at above).
            text = (await review_card.inner_text()).strip()
            if not text:
                continue

            rating = None
            rating_el = review_card.get_by_role("img", name=re.compile(r"star", re.I)).first
            if await rating_el.count():
                label = await rating_el.get_attribute("aria-label") or ""
                match = _RATING_RE.search(label)
                if match:
                    rating = int(float(match.group(1)))

            posted_at = _parse_relative_time(text)

            place.reviews.append(Review(text=text, rating=rating, posted_at=posted_at))

        # Photos reviewers attach to their reviews are NOT <img> tags — they're rendered as a
        # CSS background-image on <button class="Tya61d"> elements (a different CDN path,
        # "/grass-cs/", than the "/gps-cs-s/" Overview gallery photos above). Found only by
        # scanning computed styles live; there's no ARIA hook or <img> tag to select on. These
        # tend to be plentiful and are what the user specifically asked to pull in for the model.
        try:
            review_photo_urls = await page.evaluate(_SCAN_REVIEW_PHOTOS_JS)
        except Exception:
            review_photo_urls = []
        for url in review_photo_urls[:_MAX_REVIEW_PHOTOS_PER_PLACE]:
            upscaled = _upscale_photo_url(url)
            if not any(p.url == upscaled for p in place.photos):
                place.photos.append(Photo(url=upscaled))
