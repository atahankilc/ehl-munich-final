"""Settings from the environment (.env). Model names are never hardcoded (AGENTS rule 12)."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]  # repo root (backend/src/bmw_req/config.py)
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None
    model_fast: str
    model_smart: str
    model_embed: str
    raw_data_dir: Path
    data_dir: Path
    database_url: str | None   # PostgreSQL (D-059)

    @property
    def db_path(self) -> Path:
        """The former SQLite database (D-016) — kept read-only as the pre-D-059 backup and copy source."""
        return self.data_dir / "app.db"


def _path(var: str, default: str) -> Path:
    p = Path(os.getenv(var, default))
    return p if p.is_absolute() else ROOT / p


def get_settings() -> Settings:
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        model_fast=os.getenv("OPENAI_MODEL_FAST", "gpt-6-luna"),
        model_smart=os.getenv("OPENAI_MODEL_SMART", "gpt-6.1-sol"),
        model_embed=os.getenv("OPENAI_MODEL_EMBED", "text-embedding-3-small"),
        raw_data_dir=_path("RAW_DATA_DIR", "challange information document/BMW-Data"),
        data_dir=_path("DATA_DIR", "data"),
        database_url=os.getenv("DATABASE_URL"),
    )
