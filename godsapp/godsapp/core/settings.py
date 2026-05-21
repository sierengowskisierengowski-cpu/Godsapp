"""Application settings, persisted to ~/.config/godsapp/settings.toml."""
from __future__ import annotations

import tomllib
from typing import Optional

from pydantic import BaseModel, Field

from godsapp.core import paths


class APISettings(BaseModel):
    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = 7842
    require_token: bool = True


class UISettings(BaseModel):
    theme: str = "dark"          # "dark" | "light" | "system"
    accent: str = "cream"        # "cream" | "amber" | "ivory"
    matrix_scramble: bool = True


class DatabaseSettings(BaseModel):
    url: Optional[str] = None    # if None, falls back to local SQLite


class Settings(BaseModel):
    api: APISettings = Field(default_factory=APISettings)
    ui: UISettings = Field(default_factory=UISettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)


def load_settings() -> Settings:
    """Load settings from disk, falling back to defaults."""
    if not paths.SETTINGS_PATH.exists():
        return Settings()
    try:
        with paths.SETTINGS_PATH.open("rb") as f:
            data = tomllib.load(f)
        return Settings.model_validate(data)
    except Exception:
        # Bad config — surface in UI later, never crash on launch
        return Settings()


def save_settings(settings: Settings) -> None:
    """Persist settings to disk as TOML."""
    paths.ensure_directories()
    lines = []
    data = settings.model_dump()
    for section, values in data.items():
        lines.append(f"[{section}]")
        for k, v in values.items():
            if isinstance(v, str):
                lines.append(f'{k} = "{v}"')
            elif isinstance(v, bool):
                lines.append(f"{k} = {str(v).lower()}")
            elif v is None:
                continue
            else:
                lines.append(f"{k} = {v}")
        lines.append("")
    paths.SETTINGS_PATH.write_text("\n".join(lines))
