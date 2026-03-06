from __future__ import annotations
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, field_validator, Field
from pathlib import Path
import yaml


class GitConfig(BaseModel):
    type: Literal["git"]
    url: str
    ref: str
    ssh_key_path: Annotated[Path | None, Field(exclude=True)] = None


class FileConfig(BaseModel):
    type: Literal["file"]
    path: str


class BuildConfig(BaseModel):
    name: str
    version: str
    src: GitConfig | FileConfig | None = Field(None, discriminator="type")
    depends: list[str] = Field(default_factory=list)

    build: str


class AreaConfig(BaseModel):
    name: str
    host: str


class Config(BaseModel):
    model_config = ConfigDict(alias_generator=(lambda x: x.replace("_", "-")))

    main_package: str
    entrypoint: Path

    packages: list[BuildConfig]
    areas: list[AreaConfig] = Field(default_factory=list)
    links: dict[str, str] = Field(default_factory=dict)

    @field_validator("entrypoint")
    @classmethod
    def validate_entrypoint_is_relative(cls, value: Path) -> Path:
        if value.is_absolute():
            raise ValueError(f"Entrypoint {value} must be a relative path")
        return value


def load_config(path: Path) -> Config:
    with open(path) as f:
        return Config.model_validate(yaml.safe_load(f.read()))
