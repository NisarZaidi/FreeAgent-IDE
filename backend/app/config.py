"""Application configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "FreeAgent IDE"
    host: str = "127.0.0.1"
    port: int = 8765
    workspace_root: Path | None = None

    # Models
    ollama_base_url: str = "http://127.0.0.1:11434"
    openai_base_url: str | None = None
    openai_api_key: str | None = None
    default_provider: Literal["ollama", "openai"] = "ollama"
    default_model: str = "llama3.2:3b"
    planner_model: str | None = None
    coder_model: str | None = None
    reviewer_model: str | None = None
    tester_model: str | None = None

    # Safety
    require_write_approval: bool = True
    require_terminal_approval: bool = True
    max_undo_snapshots: int = 50

    # Hardware tier defaults (model names for Ollama)
    model_tier_low: str = "llama3.2:3b"
    model_tier_mid: str = "qwen2.5-coder:7b"
    model_tier_high: str = "qwen2.5-coder:14b"

    data_dir: Path = Field(default_factory=lambda: Path.home() / ".freeagent-ide")

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "snapshots").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "sessions").mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
