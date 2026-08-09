from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="backend/api/templates")


@router.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {})
