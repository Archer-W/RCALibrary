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
    # Use-case repos point these at their own dirs via env vars.
    templates_dir: Path = REPO_ROOT / "templates"
    samples_dir: Path = REPO_ROOT / "data" / "samples"
    frontend_dir: Path = REPO_ROOT / "frontend"

    # Saved-report cache (file-based): re-searching the same key loads the saved
    # customized report without recompute. See backend/rcalibrary/persistence/.
    report_cache_dir: Path = REPO_ROOT / "data" / "cache"
    report_cache_max_bytes: int = 4 * 1024 * 1024  # reject saved blobs larger than this

    # Use-case plugins: comma-separated importable module paths. Imported at
    # startup so their analyzers / data sources / auth provider register before
    # registries are built. See docs/07-building-use-cases.md.
    plugins: str = ""

    # Optional extra static dir served at /ext (for use-case custom panel JS).
    frontend_ext_dir: Path | None = None

    # Usage-logging placeholder.
    audit_mode: str = "noop"  # "noop" | "file"
    audit_file: Path = REPO_ROOT / "audit.jsonl"

    # Map panels: when true, the map panel uses online OpenStreetMap tiles
    # (needs internet). Default false keeps the offline blank-canvas map.
    map_tiles: bool = False

    # --- AI panel mode (fixed flow + natural-language input) -----------------
    # The AI engine parses a free-text request, picks a predefined library panel,
    # fills parameters, and builds it (see docs/11-ai-panel-builder.md). This repo
    # ships the FREE, OFFLINE `simulated` engine (deterministic parsing — no LLM,
    # no API key, no cost). The other agent connects a real LLM in its own env by
    # registering an engine for a different provider and selecting it here.
    ai_enabled: bool = True            # master switch (the template's ai_panels flag also gates the UI)
    ai_provider: str = "simulated"     # "simulated" (this repo, free/offline) | "openai"/"local"/"gpt-oss" (real LLM)
    ai_max_turns: int = 12             # safety cap on chat turns per session
    ai_session_ttl_s: int = 1800       # drop idle AI chat sessions after this many seconds
    # Real-LLM engine (used when ai_provider selects the OpenAI-compatible client — e.g.
    # a local gpt-oss endpoint served by vLLM/Ollama). The shipped simulated engine
    # needs NONE of these. See docs/11-ai-panel-builder.md + docs/handoff/ai-panel-llm/.
    ai_base_url: str = ""              # e.g. http://localhost:8000/v1  (OpenAI-compatible)
    ai_model: str = ""                # e.g. gpt-oss-20b
    ai_api_key: str = ""              # optional; most local gateways ignore it
    ai_request_timeout: int = 60      # seconds
    ai_temperature: float = 0.0       # deterministic routing
    ai_tool_choice: str = "required"  # "required" forces a tool call; use "auto" if your server rejects it

    # Server.
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: str = "*"


@lru_cache
def get_settings() -> Settings:
    return Settings()
