from __future__ import annotations
from typing import Annotated, Literal

from pydantic import BaseModel, field_validator, Field
from pathlib import Path
import yaml


class GitConfig(BaseModel):
    type: Literal["git"]
    url: str
    ref: str
    ssh_key_path: Annotated[Path | None, Field(exclude=True)] = None


class GitHubConfig(BaseModel):
    type: Literal["github"]
    owner: str
    repo: str
    ref: str
    ssh_key_path: Annotated[Path | None, Field(exclude=True)] = None


class FileConfig(BaseModel):
    type: Literal["file"]
    path: str


class BuildConfig(BaseModel):
    name: str
    version: str
    src: GitConfig | GitHubConfig | FileConfig | None = Field(
        None, discriminator="type"
    )
    depends: list[str] = Field(default_factory=list)


class EnvConfig(BaseModel):
    name: str
    dest: str


class PathConfig(BaseModel):
    store: Path

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
    areas: list[AreaConfig] = Field(default_factory=list)
    links: dict[str, dict[str, str]]


def load_config(path: Path) -> Config:
    with open(path / "config.yaml") as f:
        return Config.model_validate(yaml.safe_load(f.read()))
