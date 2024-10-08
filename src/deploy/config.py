from __future__ import annotations

from pydantic import BaseModel, field_validator, Field
from pathlib import Path
import yaml

from pydantic import DirectoryPath


class BuildConfig(BaseModel):
    name: str
    version: str
    git_url: str
    git_ref: str
    depends: list[str] = Field(default_factory=list)


class PathConfig(BaseModel):
    local_base: DirectoryPath
    system_base: DirectoryPath
    envs: Path
    store: Path

    @field_validator("local_base", "system_base", mode="before")
    @classmethod
    def _validate_base(cls, value: str) -> Path:
        dir_ = Path(value).expanduser().resolve()
        dir_.mkdir(parents=True, exist_ok=True)
        return dir_

    @field_validator("envs", "store")
    @classmethod
    def _validate_path(cls, value: Path) -> Path:
        if value.is_absolute():
            raise ValueError(f"Path {value} must be relative")
        return value


class AreaConfig(BaseModel):
    name: str
    host: str


class Config(BaseModel):
    paths: PathConfig
    builds: list[BuildConfig]
    links: dict[str, str]
    areas: list[AreaConfig]

def load_config(path: Path | None = None) -> Config:
    with open(path or Path.cwd() / "config.yaml") as f:
        return Config.model_validate(yaml.safe_load(f.read()))
