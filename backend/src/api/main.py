"""FastAPI app for the rebuilt PM frontend (replaces the Streamlit app's read/write paths, inventory §1–§4).

Localhost only (127.0.0.1:8600), no CORS: the frontend is served from the same origin (frontend/dist) or proxied by the
Vite dev server. Run with `uv run python -m api` or `uv run sharksight`.

Profiles (D-053), from the environment:
- `APP_ENV=development` (default): auto-reload on code changes in backend/src; the PM app comes from the Vite dev server.
- `APP_ENV=production`: no reload; the API serves the built app from frontend/dist.
`API_HOST` / `API_PORT` default to 127.0.0.1:8600. `API_HOST=0.0.0.0` is for containers only, where compose publishes
the port on the host's 127.0.0.1 (AGENTS rule 1). `API_RELOAD=0|1` overrides the profile's reload default.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.deps import DB
from api.routers import ROUTERS, STATIC_ROUTER
from api.routers.static import WEB_DIST
from bmw_req.config import ROOT
from bmw_req.llm import budget

PROFILES = ("development", "production")
PROFILE = os.getenv("APP_ENV", "development")
if PROFILE not in PROFILES:
    raise RuntimeError(f"APP_ENV={PROFILE!r}; expected one of {', '.join(PROFILES)}")
HOST = os.getenv("API_HOST", "127.0.0.1")   # never 0.0.0.0 outside a container: BMW-confidential data (AGENTS rule 1)
PORT = int(os.getenv("API_PORT", "8600"))
RELOAD = os.getenv("API_RELOAD", "1" if PROFILE == "development" else "0") == "1"
budget.INTERACTIVE = False   # API jobs confirm spend in the app, never on the server's terminal (D-054)

log = logging.getLogger("api")


@asynccontextmanager
async def _lifespan(app: FastAPI):
    if PROFILE == "production" and not (WEB_DIST / "index.html").exists():
        log.warning("APP_ENV=production but %s has no build; run `make build`", WEB_DIST)
    yield
    DB.close()


def create_app() -> FastAPI:
    app = FastAPI(title="Successor — PM decision API", version="1.0", lifespan=_lifespan,
                  docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)
    @app.get("/api/health", tags=["meta"])
    def health() -> dict:
        return {"ok": True, "profile": PROFILE}

    for r in ROUTERS:
        app.include_router(r)
    app.include_router(STATIC_ROUTER)   # /models + SPA catch-all, must stay last
    return app


app = create_app()


def run() -> None:
    import uvicorn

    print(f"SharkSight API: profile {PROFILE}, {HOST}:{PORT}, reload {'on' if RELOAD else 'off'}", flush=True)
    # reload restarts the process on save, which also ends any job running in it (wave, agent panel)
    uvicorn.run("api.main:app", host=HOST, port=PORT, log_level="info", reload=RELOAD,
                reload_dirs=[str(ROOT / "backend" / "src")] if RELOAD else None)


if __name__ == "__main__":
    run()
