from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from backend.api.i18n import LANG_COOKIE, request_lang, strings

router = APIRouter()
templates = Jinja2Templates(directory="backend/api/templates")


@router.get("/")
async def index(request: Request):
    lang = request_lang(request)
    response = templates.TemplateResponse(
        request, "index.html", {"lang": lang, "t": strings(lang)}
    )
    # Remember the toggle choice so a plain "/" visit keeps the same language.
    response.set_cookie(LANG_COOKIE, lang, max_age=365 * 24 * 3600, samesite="lax")
    return response
