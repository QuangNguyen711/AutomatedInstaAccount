from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.api.v1 import page_router, search_router

app = FastAPI(title="PlacesFinder")

app.mount("/static", StaticFiles(directory="backend/api/static"), name="static")

app.include_router(page_router.router)
app.include_router(search_router.router)
