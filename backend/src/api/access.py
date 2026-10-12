"""One shared access key in front of the whole app (cloud deployment, D-063): no user accounts, no login page.

If `ACCESS_KEY` is set, every request except `/api/health` must carry it as the password of HTTP Basic auth (any user
name). The browser asks once, then sends it with every request of the page (API calls, 3D models). Without the
variable — locally — nothing changes. The key is compared in constant time and never logged.
"""

from __future__ import annotations

import base64
import binascii
import os
import secrets

from fastapi import Request
from fastapi.responses import PlainTextResponse

OPEN_PATHS = ("/api/health",)   # the host's health check


def _password(header: str | None) -> str | None:
    if not header or not header.lower().startswith("basic "):
        return None
    try:
        decoded = base64.b64decode(header[6:].strip(), validate=True).decode()
    except (binascii.Error, UnicodeDecodeError):
        return None
    return decoded.partition(":")[2]


async def require_access_key(request: Request, call_next):
    key = os.getenv("ACCESS_KEY")
    if not key or request.url.path in OPEN_PATHS:
        return await call_next(request)
    given = _password(request.headers.get("authorization"))
    if given is not None and secrets.compare_digest(given.encode(), key.encode()):
        return await call_next(request)
    return PlainTextResponse("SharkSight: access key required", status_code=401,
                             headers={"WWW-Authenticate": 'Basic realm="SharkSight", charset="UTF-8"'})
