"""FastAPI app for the rebuilt PM frontend (replaces the Streamlit app's read/write paths, inventory §1–§4).

Localhost only (127.0.0.1:8600), no CORS: the frontend is served from the same origin (web/dist) or proxied by the
Vite dev server. Run with `uv run python -m api` or `uv run successor`.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.deps import DB
from api.routers import ROUTERS, STATIC_ROUTER

HOST = "127.0.0.1"   # never 0.0.0.0: the data is BMW-confidential (AGENTS rule 1)
PORT = 8600


@asynccontextmanager
async def _lifespan(app: FastAPI):
    yield
    DB.close()


def create_app() -> FastAPI:
    app = FastAPI(title="Successor — PM decision API", version="1.0", lifespan=_lifespan,
                  docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)
    for r in ROUTERS:
        app.include_router(r)
    app.include_router(STATIC_ROUTER)   # /models + SPA catch-all, must stay last
    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("api.main:app", host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    run()
