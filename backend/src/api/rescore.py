"""Background worker for the automatic prioritize re-score (`bmw_req.prioritize.auto`).

PM actions (decision, proposal verdict, weights, ladder rung, link review) call `queue(cp, trigger, include_self)` AFTER
their transaction committed and return `{"rescore": "queued"}` at once. One worker thread at a time, on its OWN database
connection; requests that arrive while it runs are coalesced into one follow-up pass that starts at the earliest
requested checkpoint (re-running from there covers every later one). `status()` is exposed in GET /api/prioritize.

MODE (env PRIO_AUTO_RESCORE): "thread" (API default), "sync" (run inline — tests), "off" (do nothing; default under pytest).
"""

from __future__ import annotations

import logging
import os
import sys
import threading
from datetime import datetime, timezone

from bmw_req import checkpoints as C

# under pytest the default is "off" (no stray threads writing to a test's temp DB); tests opt in with "sync"
MODE = os.environ.get("PRIO_AUTO_RESCORE") or ("off" if "pytest" in sys.modules else "thread")
_LOCK = threading.Lock()
_STATE: dict = {"running": False, "pending": None, "seq": 0, "done": 0, "last": None, "error": None}
log = logging.getLogger("bmw_req.prioritize.auto")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _merge(pending: dict | None, cp: str | None, trigger: str, include_self: bool) -> dict:
    """Coalesce: start = the earliest checkpoint any request needs re-run (None = from the first)."""
    pos = (C.BY_ID[cp].position if cp in C.BY_ID else 0) + (0 if include_self or cp not in C.BY_ID else 0.5)
    if pending is None or pos < pending["pos"]:
        new = {"pos": pos, "cp": cp, "include_self": include_self}
    else:
        new = {k: pending[k] for k in ("pos", "cp", "include_self")}
    new["triggers"] = (pending["triggers"] if pending else []) + [trigger]
    return new


def _run_once(job: dict) -> list[dict]:
    from bmw_req.db import connect
    from bmw_req.prioritize.auto import rescore

    conn = connect()
    try:
        return rescore(conn, job["cp"], "+".join(dict.fromkeys(job["triggers"])), job["include_self"])
    finally:
        conn.close()


def _worker() -> None:
    while True:
        with _LOCK:
            job = _STATE["pending"]
            if job is None:
                _STATE["running"] = False
                return
            _STATE["pending"] = None
        try:
            out = _run_once(job)
            with _LOCK:
                _STATE.update(done=_STATE["done"] + len(job["triggers"]), error=None,
                              last={"at": _now(), "triggers": job["triggers"], "from": job["cp"], "runs": out})
        except Exception as e:   # surfaced in status(); the next PM action retries
            log.exception("auto re-score failed")
            with _LOCK:
                _STATE.update(done=_STATE["done"] + len(job["triggers"]), error=f"{type(e).__name__}: {e}")


def queue(cp: str | None, trigger: str, include_self: bool = True) -> str:
    """Schedule a re-score from `cp` (and every later checkpoint). Returns "queued" | "sync" | "off" | "none"."""
    if MODE == "off":
        return "off"
    if cp in C.BY_ID and not include_self and C.BY_ID[cp].position == max(c.position for c in C.CHECKPOINTS):
        return "none"   # nothing later to re-score
    if MODE == "sync":
        _run_once({"cp": cp, "triggers": [trigger], "include_self": include_self})
        return "sync"
    with _LOCK:
        _STATE["seq"] += 1
        _STATE["pending"] = _merge(_STATE["pending"], cp, trigger, include_self)
        if _STATE["running"]:
            return "queued"
        _STATE["running"] = True
    threading.Thread(target=_worker, name="prio-rescore", daemon=True).start()
    return "queued"


def status() -> dict:
    with _LOCK:
        busy = _STATE["running"] or _STATE["pending"] is not None
        return {"state": "running" if busy else "idle", "seq": _STATE["seq"], "done": _STATE["done"],
                "last": _STATE["last"], "error": _STATE["error"]}
