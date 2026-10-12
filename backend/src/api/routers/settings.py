"""Run-time settings (D-054): the OpenAI API key and the budget limits, set from the app's Usage tab.

The key is never returned — only whether one is set, where it comes from and a masked form. Saving a key first checks
it against OpenAI with a free call (`models.list`). Every change is an audit event (AGENTS rule 6); the key itself is
never written to the audit trail, only its masked form.
"""

from __future__ import annotations

import openai
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import db, get_actor
from bmw_req import app_settings
from bmw_req.llm import budget
from bmw_req.audit import audit

router = APIRouter(prefix="/api/settings", tags=["settings"])


class KeyBody(BaseModel):
    key: str


class BudgetBody(BaseModel):
    confirm_above_usd: float
    stop_at_usd: float


def _state() -> dict:
    limits = app_settings.budget_limits()
    with db() as conn:
        spent, committed = budget.spent_usd(conn), budget.committed_usd(conn)
    return {
        "openai": {"configured": app_settings.api_key() is not None, "source": app_settings.key_source(),
                   "masked": app_settings.mask(app_settings.api_key())},
        "budget": {"confirm_above_usd": limits.confirm_above_usd, "stop_at_usd": limits.stop_at_usd,
                   "spent_usd": round(spent, 4), "committed_usd": round(committed, 4),
                   "asking": committed > limits.confirm_above_usd, "stopped": committed >= limits.stop_at_usd},
    }


def verify_key(key: str) -> None:
    """Free check that OpenAI accepts the key (raises HTTP 400 if not). Patched in tests."""
    try:
        openai.OpenAI(api_key=key, timeout=10, max_retries=0).models.list()
    except openai.AuthenticationError as e:
        raise HTTPException(400, "OpenAI rejected this key.") from e
    except openai.APIError as e:
        raise HTTPException(502, f"Couldn't reach OpenAI to check the key ({type(e).__name__}); nothing was saved.") from e


@router.get("")
def get_settings() -> dict:
    return _state()


@router.put("/openai-key")
def set_key(body: KeyBody, actor: str = Depends(get_actor)) -> dict:
    try:
        key = app_settings.check_key_format(body.key)   # before the network call
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    old = app_settings.mask(app_settings.api_key())
    verify_key(key)
    app_settings.set_api_key(key)
    with db() as conn:
        audit(conn, actor_type="human", actor_id=actor, action="set_api_key", entity_type="setting",
              entity_id="openai_api_key", old=old, new=app_settings.mask(key), rationale="Key checked with OpenAI")
    return _state()


@router.delete("/openai-key")
def remove_key(actor: str = Depends(get_actor)) -> dict:
    old = app_settings.mask(app_settings.load().get("openai_api_key"))
    app_settings.set_api_key(None)
    with db() as conn:
        audit(conn, actor_type="human", actor_id=actor, action="remove_api_key", entity_type="setting",
              entity_id="openai_api_key", old=old, new=app_settings.mask(app_settings.api_key()),
              rationale="Falls back to OPENAI_API_KEY from .env")
    return _state()


@router.put("/budget")
def set_budget(body: BudgetBody, actor: str = Depends(get_actor)) -> dict:
    old = app_settings.budget_limits()
    try:
        new = app_settings.set_budget_limits(body.confirm_above_usd, body.stop_at_usd)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    with db() as conn:
        audit(conn, actor_type="human", actor_id=actor, action="set_budget", entity_type="setting",
              entity_id="budget", old={"confirm_above_usd": old.confirm_above_usd, "stop_at_usd": old.stop_at_usd},
              new={"confirm_above_usd": new.confirm_above_usd, "stop_at_usd": new.stop_at_usd})
    return _state()
