"""In-memory background jobs for the two long, paid pipeline actions: opening a wave and a PM challenge.

One job at a time (both spend OpenAI budget and write a lot). Each job runs in its own thread with its OWN SQLite
connection — the pipeline opens its own anyway — so the shared API connection stays free for reads. Log lines from the
pipeline's return value and from `bmw_req` loggers are captured into the job record.

The pipeline functions are looked up on their modules at call time (`graph.advance`, `challenge.challenge`,
`make_llm`) so tests can monkeypatch them — tests must never trigger a paid call.
"""

from __future__ import annotations

import itertools
import logging
import threading
import traceback
from datetime import datetime, timezone
from typing import Any, Callable

_LOCK = threading.Lock()
_JOBS: dict[str, dict] = {}
_IDS = itertools.count(1)
MAX_KEEP = 50


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class _Capture(logging.Handler):
    def __init__(self, job: dict):
        super().__init__(level=logging.INFO)
        self.job = job

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.job["log"].append(f"{record.levelname.lower()}: {record.getMessage()}")
        except Exception:
            pass


def running() -> dict | None:
    with _LOCK:
        for j in _JOBS.values():
            if j["status"] == "running":
                return {"id": j["id"], "kind": j["kind"]}
    return None


def get(job_id: str) -> dict | None:
    with _LOCK:
        j = _JOBS.get(job_id)
        return None if j is None else {**j, "log": list(j["log"])}


def start(kind: str, fn: Callable[[Callable[[str], None]], Any], meta: dict | None = None) -> str | None:
    """Start `fn(log)` in a background thread. Returns the job id, or None when another job is running."""
    with _LOCK:
        if any(j["status"] == "running" for j in _JOBS.values()):
            return None
        jid = f"{kind}-{next(_IDS)}"
        job = {"id": jid, "kind": kind, "status": "running", "started_at": _now(), "finished_at": None,
               "log": [], "error": None, "result": None, "meta": meta or {}}
        _JOBS[jid] = job
        if len(_JOBS) > MAX_KEEP:
            for old in [k for k, v in _JOBS.items() if v["status"] != "running"][: len(_JOBS) - MAX_KEEP]:
                _JOBS.pop(old, None)

    def log(line: str) -> None:
        job["log"].append(str(line))

    def target() -> None:
        handler = _Capture(job)
        logger = logging.getLogger("bmw_req")
        logger.addHandler(handler)
        prev_level = logger.level
        if logger.level == logging.NOTSET or logger.level > logging.INFO:
            logger.setLevel(logging.INFO)
        try:
            result = fn(log)
            with _LOCK:
                job["result"] = result
                job["status"] = "done"
        except Exception as e:   # surface the failure in the job record
            with _LOCK:
                job["error"] = f"{type(e).__name__}: {e}"
                job["status"] = "error"
            job["log"].append("".join(traceback.format_exception_only(type(e), e)).strip())
        finally:
            logger.removeHandler(handler)
            logger.setLevel(prev_level)
            job["finished_at"] = _now()

    threading.Thread(target=target, name=f"job-{jid}", daemon=True).start()
    return jid


def wait(job_id: str, timeout: float = 10.0) -> dict | None:
    """Test helper: block until the job finishes (or timeout)."""
    import time

    end = time.monotonic() + timeout
    while time.monotonic() < end:
        j = get(job_id)
        if j is None or j["status"] != "running":
            return j
        time.sleep(0.02)
    return get(job_id)


# ------------------------------------------------------------------------------------------------ runners
def make_llm(conn):
    """Budget-guarded OpenAI wrapper on the job's own connection (patched in tests)."""
    from bmw_req.llm import LLM

    return LLM(conn=conn)


def run_wave(wave: int, actor: str) -> Callable[[Callable[[str], None]], dict]:
    def fn(log: Callable[[str], None]) -> dict:
        from bmw_req.pipeline import graph

        log(f"opening wave {wave} as {actor} (LLM calls are budget-guarded; replays hit the cache)")
        out = graph.advance(wave, initiated_by=actor)
        for line in out.get("log") or []:
            log(line)
        return {"wave": out.get("wave", wave), "new_requirements": list(out.get("new_requirements") or []),
                "run_id": out.get("run_id")}
    return fn


def run_challenge(req_id: str, question: str, actor: str) -> Callable[[Callable[[str], None]], dict]:
    def fn(log: Callable[[str], None]) -> dict:
        from bmw_req.db import connect
        from bmw_req.pipeline import challenge

        conn = connect()
        try:
            log(f"challenge on {req_id} by {actor}: asking the reasoning model (status → challenged)")
            out = challenge.challenge(conn, make_llm(conn), req_id, question, actor)
            log(f"answered: verdict {(out.get('answer') or {}).get('verdict')}, "
                f"cost ${float(out.get('cost') or 0):.4f}{' (cached)' if out.get('cached') else ''}")
            return out
        finally:
            conn.close()
    return fn
