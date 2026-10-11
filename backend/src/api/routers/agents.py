"""The AI agents page (D-055): every agent of the checkpoint pipeline with its configuration and its real usage, the model
tiers and the priced models. The source of truth the LLM wrapper reads on every call (`bmw_req.llm.agents`,
`bmw_req.app_settings`). Every change is an audit event (entity `setting`).
"""

from __future__ import annotations

import re
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.deps import db, get_actor
from bmw_req import app_settings
from bmw_req.llm import agents as A
from bmw_req.llm import pricing
from bmw_req.pipeline.requirements import audit

router = APIRouter(prefix="/api/agents", tags=["agents"])

CHECKPOINT = re.compile(r":(cp1|cp2)\b")
MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{1,80}$")


class AgentBody(BaseModel):
    model: str | None = None
    reasoning_effort: str | None = None
    enabled: bool = True
    cap_usd: float | None = None


class TiersBody(BaseModel):
    fast: str | None = None
    smart: str | None = None
    embed: str | None = None


class ModelBody(BaseModel):
    id: str
    kind: str = Field(pattern="^(responses|embeddings)$")
    input: float = Field(ge=0, le=1000)
    cached_input: float = Field(ge=0, le=1000)
    output: float = Field(ge=0, le=1000)


def _cfg(c: app_settings.AgentConfig) -> dict:
    return {"model": c.model, "reasoning_effort": c.reasoning_effort, "enabled": c.enabled, "cap_usd": c.cap_usd}


def _usage() -> tuple[dict, dict]:
    """Per agent and for the earlier pipeline: committed USD, calls, failures, tokens, last call, USD per checkpoint."""
    per: dict[str, dict] = defaultdict(lambda: {"usd": 0.0, "calls": 0, "failed": 0, "running": 0, "input_tokens": 0,
                                                "output_tokens": 0, "last": None, "by_checkpoint": defaultdict(float)})
    with db() as conn:
        rows = conn.execute("""SELECT job, status, COUNT(*) n, SUM(CASE WHEN status = 'reserved' THEN reserved_usd ELSE cost_usd END) usd,
                                      SUM(COALESCE(input_tokens, 0)) tin, SUM(COALESCE(output_tokens, 0)) tout, MAX(created_at) last
                               FROM llm_usage GROUP BY job, status""").fetchall()
    for r in rows:
        a = A.match(r["job"])
        u = per[a.key if a else "_legacy"]
        u["usd"] += r["usd"] or 0.0
        u["calls"] += r["n"]
        u["failed"] += r["n"] if r["status"] == "failed" else 0
        u["running"] += r["n"] if r["status"] == "reserved" else 0
        u["input_tokens"] += r["tin"]
        u["output_tokens"] += r["tout"]
        u["last"] = max(filter(None, [u["last"], r["last"]]), default=None)
        cp = CHECKPOINT.search(r["job"])
        u["by_checkpoint"][cp.group(1) if cp else "none"] += r["usd"] or 0.0
    out = {k: {**v, "usd": round(v["usd"], 4), "by_checkpoint": {c: round(x, 4) for c, x in v["by_checkpoint"].items()}}
           for k, v in per.items()}
    empty = {"usd": 0.0, "calls": 0, "failed": 0, "running": 0, "input_tokens": 0, "output_tokens": 0, "last": None, "by_checkpoint": {}}
    return out, empty


def _state() -> dict:
    usage, empty = _usage()
    tiers = {t: {"model": app_settings.tier_model(t), "default": getattr(app_settings.get_settings(), env),
                 "set_in_app": bool((app_settings.load().get("tiers") or {}).get(t))}
             for t, env in app_settings.TIER_ENV.items()}
    in_use: dict[str, list[str]] = defaultdict(list)
    pipes = []
    for key, label, about in A.PIPELINES:
        rows = []
        for a in (x for x in A.AGENTS if x.pipeline == key):
            cfg = app_settings.agent_config(a.key)
            effective = cfg.model or tiers[a.tier]["model"]
            in_use[effective].append(a.name)
            rows.append({"key": a.key, "name": a.name, "description": a.description, "kind": a.kind, "tier": a.tier,
                         "web_search": a.web_search, "default_effort": a.effort, "default_model": tiers[a.tier]["model"],
                         "model": effective, "effort": cfg.reasoning_effort or a.effort, "config": _cfg(cfg),
                         "usage": usage.get(a.key, empty)})
        pipes.append({"key": key, "label": label, "about": about, "agents": rows,
                      "usd": round(sum(r["usage"]["usd"] for r in rows), 4)})
    for t in tiers.values():
        in_use[t["model"]].append("tier")
    custom = app_settings.custom_models()
    models = [{"id": m, "kind": pricing.kind_of(m), "input": p.input, "cached_input": p.cached_input, "output": p.output,
               "builtin": m in pricing.PRICES, "used_by": sorted(set(in_use.get(m, [])) - {"tier"}),
               "tier": [t for t, v in tiers.items() if v["model"] == m]}
              for m, p in sorted(pricing.all_prices().items())]
    return {"pipelines": pipes, "tiers": tiers, "models": models, "efforts": list(A.EFFORTS),
            "legacy": usage.get("_legacy", empty), "custom_models": sorted(custom), "flex_factor": pricing.FLEX_FACTOR}


def _audit(actor: str, entity_id: str, old, new, action: str = "set_agent") -> None:
    with db() as conn:
        audit(conn, actor_type="human", actor_id=actor, action=action, entity_type="setting", entity_id=entity_id,
              old=old, new=new)


def _bad(e: ValueError) -> HTTPException:
    return HTTPException(400, str(e))


@router.get("")
def get_agents() -> dict:
    return _state()


@router.put("/tiers")
def set_tiers(body: TiersBody, actor: str = Depends(get_actor)) -> dict:
    old = {t: app_settings.tier_model(t) for t in app_settings.TIER_ENV}
    wanted = {t: getattr(body, t) or None for t in app_settings.TIER_ENV}
    for t, m in wanted.items():   # validate all before saving any
        if m is not None and pricing.kind_of(m) != ("embeddings" if t == "embed" else "responses"):
            raise HTTPException(400, f"{m!r} is not a priced model for the {t} tier.")
    for t, m in wanted.items():
        default = getattr(app_settings.get_settings(), app_settings.TIER_ENV[t])
        app_settings.set_tier_model(t, None if m in (None, default) else m)   # the .env default is stored as "unset"
    _audit(actor, "model_tiers", old, {t: app_settings.tier_model(t) for t in app_settings.TIER_ENV}, "set_model_tiers")
    return _state()


@router.put("/{key}")
def set_agent(key: str, body: AgentBody, actor: str = Depends(get_actor)) -> dict:
    if key not in A.BY_KEY:
        raise HTTPException(404, f"No agent {key!r}")
    old = _cfg(app_settings.agent_config(key))
    try:
        app_settings.set_agent_config(key, app_settings.AgentConfig(body.model or None, body.reasoning_effort or None,
                                                                   body.enabled, body.cap_usd))
    except ValueError as e:
        raise _bad(e) from e
    _audit(actor, f"agent:{key}", old, _cfg(app_settings.agent_config(key)))
    return _state()


@router.post("/models")
def add_model(body: ModelBody, actor: str = Depends(get_actor)) -> dict:
    if not MODEL_ID.match(body.id):
        raise HTTPException(400, "Use the model's exact OpenAI id (letters, digits, . _ : -).")
    if body.id in pricing.PRICES:
        raise HTTPException(409, f"{body.id} is built in; its price is kept in code (D-014).")
    spec = {"kind": body.kind, "input": body.input, "cached_input": body.cached_input, "output": body.output}
    old = app_settings.custom_models().get(body.id)
    app_settings.set_custom_model(body.id, spec)
    _audit(actor, f"model:{body.id}", old, spec, "set_model_price")
    return _state()


@router.delete("/models/{model_id}")
def remove_model(model_id: str, actor: str = Depends(get_actor)) -> dict:
    spec = app_settings.custom_models().get(model_id)
    if spec is None:
        raise HTTPException(404, f"{model_id} is not a model added in the app.")
    users = next((m["used_by"] + m["tier"] for m in _state()["models"] if m["id"] == model_id), [])
    if users:
        raise HTTPException(409, f"{model_id} is still in use ({', '.join(users)}); switch those to another model first.")
    app_settings.set_custom_model(model_id, None)
    _audit(actor, f"model:{model_id}", spec, None, "remove_model")
    return _state()
