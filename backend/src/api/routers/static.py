"""Static files: self-hosted 3D models from `$DATA_DIR/models/` and, in production mode, the built SPA (`frontend/dist`).

Both resolve the requested path inside their root and refuse anything that escapes it (path traversal).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from bmw_req.config import ROOT, get_settings

router = APIRouter(tags=["static"])

MEDIA_TYPES = {
    ".glb": "model/gltf-binary", ".gltf": "model/gltf+json", ".bin": "application/octet-stream",
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".ktx2": "image/ktx2",
    ".json": "application/json",
}
WEB_DIST = ROOT / "frontend" / "dist"


def safe_file(root: Path, rel: str) -> Path | None:
    """`root/rel` if it is an existing regular file inside `root` (symlinks resolved), else None."""
    if not rel or "\x00" in rel:
        return None
    try:
        base = root.resolve(strict=True)
        p = (base / rel).resolve(strict=True)
    except (FileNotFoundError, OSError, RuntimeError):
        return None
    if not p.is_relative_to(base) or not p.is_file():
        return None
    return p


@router.get("/models/{path:path}", include_in_schema=False)
def models(path: str) -> FileResponse:
    p = safe_file(get_settings().data_dir / "models", path)
    if p is None or p.suffix.lower() not in MEDIA_TYPES:
        raise HTTPException(404, "Not found")
    return FileResponse(p, media_type=MEDIA_TYPES[p.suffix.lower()], headers={"Cache-Control": "public, max-age=3600"})


@router.get("/{path:path}", include_in_schema=False)
def spa(path: str) -> FileResponse:
    """Serve `frontend/dist` with SPA fallback to index.html for client-side routes (never for /api or /models)."""
    if path == "api" or path.startswith(("api/", "models/")) or path == "models":
        raise HTTPException(404, "Not found")
    index = WEB_DIST / "index.html"
    if not index.is_file():
        raise HTTPException(404, "Frontend not built (run the web build to create frontend/dist)")
    p = safe_file(WEB_DIST, path) if path else None
    if p is not None:
        return FileResponse(p)
    if Path(path).suffix:   # a missing asset is a 404, not the app shell
        raise HTTPException(404, "Not found")
    return FileResponse(index, headers={"Cache-Control": "no-cache"})
