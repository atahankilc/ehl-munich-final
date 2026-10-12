"""One shared access key for changes (cloud deployment, D-063): no user accounts, no login page.

If `ACCESS_KEY` is set, anyone can read (GET) but every request that changes something — PM decisions, weights,
settings, the OpenAI key, agent settings — must carry the key in `X-Access-Key`; without it the API does nothing
(403). The PM app's "Access" panel (bottom left) stores the key in the browser and sends it with every request.
`POST /api/prioritize/preview` only computes and stays open. Without the variable — locally — nothing changes.
The key is compared in constant time and never logged.
"""

from __future__ import annotations

import os
import secrets

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

HEADER = "x-access-key"
READ_METHODS = ("GET", "HEAD", "OPTIONS")
READ_ONLY_POSTS = ("/api/prioritize/preview",)   # computes in memory, writes nothing

router = APIRouter(prefix="/api", tags=["meta"])


def _required() -> str | None:
    return os.getenv("ACCESS_KEY") or None


def _valid(request: Request, key: str) -> bool:
    given = request.headers.get(HEADER)
    return given is not None and secrets.compare_digest(given.encode(), key.encode())


async def require_access_key(request: Request, call_next):
    key = _required()
    if not key or request.method in READ_METHODS or request.url.path in READ_ONLY_POSTS or _valid(request, key):
        return await call_next(request)
    return JSONResponse({"detail": "Read-only: enter the access key under Access (bottom left) to make changes."},
                        status_code=403)


@router.get("/access")
def access(request: Request) -> dict:
    """Whether changes need a key here, and whether the key this browser sends is right."""
    key = _required()
    return {"required": key is not None, "valid": key is None or _valid(request, key)}
