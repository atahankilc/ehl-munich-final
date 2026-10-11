"""Settings the user changes at run time: the OpenAI API key and budget limits (D-054); per-agent configuration, model
tiers and extra models with their prices (D-055, the "AI agents" page).

Stored in `$DATA_DIR/settings.json` (git-ignored, owner-only 0600), outside `app.db` so a snapshot restore never
touches it. `APP_SETTINGS_FILE` overrides the path (tests point it at a temp file).

- API key: the key saved here wins over `OPENAI_API_KEY` from `.env` / the environment. Never returned in full —
  callers show `mask()`.
- Budget (on committed spend = settled cost + open reservations, see `llm.budget`):
  `confirm_above_usd` — above this, a run must be confirmed before it spends (terminal prompt or the app's confirm);
  `stop_at_usd` — hard stop, no call may cross it.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path

from bmw_req.config import get_settings

DEFAULT_CONFIRM_ABOVE_USD = 45.0
DEFAULT_STOP_AT_USD = 90.0
MAX_STOP_AT_USD = 10_000.0

_LOCK = threading.Lock()


@dataclass(frozen=True)
class BudgetLimits:
    confirm_above_usd: float
    stop_at_usd: float


def path() -> Path:
    override = os.getenv("APP_SETTINGS_FILE")
    return Path(override) if override else get_settings().data_dir / "settings.json"


def load() -> dict:
    try:
        data = json.loads(path().read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _save(data: dict) -> None:
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, p)
    os.chmod(p, 0o600)


def _update(**changes) -> None:
    with _LOCK:
        data = load()
        for k, v in changes.items():
            if v is None:
                data.pop(k, None)
            else:
                data[k] = v
        _save(data)


# ------------------------------------------------------------------------------------------------ API key
def api_key() -> str | None:
    return load().get("openai_api_key") or get_settings().openai_api_key or None


def key_source() -> str | None:
    """'app' (saved in settings.json), 'env' (.env / environment) or None."""
    if load().get("openai_api_key"):
        return "app"
    return "env" if get_settings().openai_api_key else None


def mask(key: str | None) -> str | None:
    if not key:
        return None
    return f"{key[:3]}…{key[-4:]}" if len(key) > 10 else "…"


def check_key_format(key: str) -> str:
    key = key.strip()
    if len(key) < 20 or any(c.isspace() for c in key):
        raise ValueError("That doesn't look like an OpenAI API key.")
    return key


def set_api_key(key: str | None) -> None:
    """Save the key (None removes it, falling back to `.env`)."""
    _update(openai_api_key=check_key_format(key) if key else None)


# ------------------------------------------------------------------------------------------------ budget
def budget_limits() -> BudgetLimits:
    b = load().get("budget") or {}
    return BudgetLimits(float(b.get("confirm_above_usd", DEFAULT_CONFIRM_ABOVE_USD)),
                        float(b.get("stop_at_usd", DEFAULT_STOP_AT_USD)))


def set_budget_limits(confirm_above_usd: float, stop_at_usd: float) -> BudgetLimits:
    if not 0 < stop_at_usd <= MAX_STOP_AT_USD:
        raise ValueError(f"The stop must be between $0 and ${MAX_STOP_AT_USD:,.0f}.")
    if not 0 <= confirm_above_usd <= stop_at_usd:
        raise ValueError("Ask-before-spending must be between $0 and the stop.")
    limits = BudgetLimits(round(confirm_above_usd, 2), round(stop_at_usd, 2))
    _update(budget={"confirm_above_usd": limits.confirm_above_usd, "stop_at_usd": limits.stop_at_usd})
    return limits


# ------------------------------------------------------------------------------------------------ agents (D-055)
@dataclass(frozen=True)
class AgentConfig:
    model: str | None = None              # None = the tier's model
    reasoning_effort: str | None = None   # None = what the code passes
    enabled: bool = True
    cap_usd: float | None = None          # total committed spend of this agent; None = no cap


def agent_config(key: str) -> AgentConfig:
    c = (load().get("agents") or {}).get(key) or {}
    return AgentConfig(c.get("model"), c.get("reasoning_effort"), bool(c.get("enabled", True)),
                       None if c.get("cap_usd") is None else float(c["cap_usd"]))


def set_agent_config(key: str, cfg: AgentConfig) -> None:
    from bmw_req.llm import agents, pricing

    agent = agents.BY_KEY.get(key)
    if agent is None:
        raise ValueError(f"Unknown agent {key!r}.")
    if cfg.model is not None and pricing.kind_of(cfg.model) != agent.kind:
        raise ValueError(f"{cfg.model!r} is not a priced {agent.kind} model.")
    if cfg.reasoning_effort is not None and (agent.kind != "responses" or cfg.reasoning_effort not in agents.EFFORTS):
        raise ValueError("Reasoning effort must be low, medium or high (text models only).")
    if cfg.cap_usd is not None and not 0 <= cfg.cap_usd <= MAX_STOP_AT_USD:
        raise ValueError("The cap must be between $0 and the maximum stop.")
    with _LOCK:
        data = load()
        all_ = data.setdefault("agents", {})
        entry = {k: v for k, v in {"model": cfg.model, "reasoning_effort": cfg.reasoning_effort,
                                   "enabled": None if cfg.enabled else False,
                                   "cap_usd": cfg.cap_usd}.items() if v is not None}
        if entry:
            all_[key] = entry
        else:
            all_.pop(key, None)   # back to the code's defaults
        _save(data)


TIER_ENV = {"fast": "model_fast", "smart": "model_smart", "embed": "model_embed"}


def tier_model(tier: str) -> str:
    """The model behind a tier: set in the app, else OPENAI_MODEL_* from .env."""
    return (load().get("tiers") or {}).get(tier) or getattr(get_settings(), TIER_ENV[tier])


def set_tier_model(tier: str, model: str | None) -> None:
    from bmw_req.llm import pricing

    if tier not in TIER_ENV:
        raise ValueError(f"Unknown tier {tier!r}.")
    if model is not None and pricing.kind_of(model) != ("embeddings" if tier == "embed" else "responses"):
        raise ValueError(f"{model!r} is not a priced model for the {tier} tier.")
    with _LOCK:
        data = load()
        tiers = data.setdefault("tiers", {})
        if model is None:
            tiers.pop(tier, None)
        else:
            tiers[tier] = model
        _save(data)


def custom_models() -> dict[str, dict]:
    """Models added in the app: {id: {kind, input, cached_input, output}} (USD per 1M tokens)."""
    return load().get("models") or {}


def set_custom_model(model_id: str, spec: dict | None) -> None:
    with _LOCK:
        data = load()
        models = data.setdefault("models", {})
        if spec is None:
            models.pop(model_id, None)
        else:
            models[model_id] = spec
        _save(data)
