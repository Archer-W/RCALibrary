"""Application configuration (pydantic-settings).

All settings are read from the environment with the ``RCA_`` prefix (or a
``.env`` file). Path defaults resolve relative to the repository root so the
app runs out of the box against the bundled sample data.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# config.py -> rcalibrary -> backend -> <repo root>
REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RCA_", env_file=".env", extra="ignore")

    # Active data source: "sample" (offline CSV) or "snowflake" (Phase 2).
    datasource: str = "sample"

    # Locations (templates + sample data are *data*, kept outside the code tree).
    templates_dir: Path = REPO_ROOT / "templates"
    samples_dir: Path = REPO_ROOT / "data" / "samples"
    frontend_dir: Path = REPO_ROOT / "frontend"

    # Usage-logging placeholder.
    audit_mode: str = "noop"  # "noop" | "file"
    audit_file: Path = REPO_ROOT / "audit.jsonl"

    # Server.
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: str = "*"


@lru_cache
def get_settings() -> Settings:
    return Settings()
