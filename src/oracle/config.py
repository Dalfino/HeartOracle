"""Typed configuration from environment variables (PRD-002 §5)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All knobs from PRD §5. `.env` supported; real env vars win."""

    model_config = SettingsConfigDict(
        env_prefix="ORACLE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    model_dir: Path = Path("./models")
    data_dir: Path = Path("./data")
    kb_dir: Path = Path("./kb")
    llm_path: Path = Path("./models/phi35.Q4_K_M.gguf")
    vault_path: Path = Path("./vault.db")
    vault_key: str = ""
    analytics: bool = False
    dev_llm: bool = False
    threads: int = 4
    log_level: str = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor."""
    return Settings()


def reset_settings_cache() -> None:
    """Drop the cached settings (used by tests to re-read mutated env)."""
    get_settings.cache_clear()
