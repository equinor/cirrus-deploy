from __future__ import annotations
from typing import Literal

from pydantic import BaseModel, field_validator, Field
from pathlib import Path
import yaml

from pydantic import DirectoryPath


class GitConfig(BaseModel):
    type: Literal["git"]
    url: str
    ref: str
    ssh_key_path: Path | None


class FileConfig(BaseModel):
    type: Literal["file"]
    path: str


class BuildConfig(BaseModel):
    name: str
    version: str
    src: GitConfig | FileConfig
    depends: list[str] = Field(default_factory=list)


class EnvConfig(BaseModel):
    name: str
    dest: str


class PathConfig(BaseModel):
    local_base: DirectoryPath
    system_base: str
    store: Path

    @field_validator("local_base", mode="before")
    @classmethod
    def _validate_base(cls, value: str) -> Path:
        dir_ = Path(value).expanduser().resolve()
        (dir_ / "versions" / ".store").mkdir(parents=True, exist_ok=True)
        (dir_ / "bin").mkdir(parents=True, exist_ok=True)
        return dir_

    @field_validator("store")
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
    envs: list[EnvConfig]
    areas: list[AreaConfig]
    links: dict[str, dict[str, str]]


def load_config(path: Path) -> Config:
    with open(path / "config.yaml") as f:
        return Config.model_validate(yaml.safe_load(f.read()))
