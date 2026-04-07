from __future__ import annotations
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    FilePath,
    field_validator,
    Field,
    model_validator,
)
from pathlib import Path
import pydantic
import yaml


def get_default_output_path() -> Path:
    return Path("output")


class Config(BaseModel):
    """Main configuration model"""

    model_config = ConfigDict(alias_generator=(lambda x: x.replace("_", "-")))

    main_package: str = Field(description="Name of primary package (eg: 'hello')")
    entrypoint: Path = Field(
        description="Relative path to main executable to wrap in the run script (eg: 'bin/hello')"
    )
    build_image: FilePath = Field(
        description="Path to containerfile to use for building (eg: './Containerfile')"
    )

    packages: list[PackageConfig] = Field(description="List of packages to build")
    areas: list[AreaConfig] = Field(
        default_factory=list, description="Areas to sync build artifacts to"
    )
    links: dict[str, str] = Field(
        default_factory=dict, description="Symbolic links setup"
    )

    @field_validator("entrypoint")
    @classmethod
    def validate_entrypoint_is_relative(cls, value: Path) -> Path:
        if value.is_absolute():
            raise ValueError(f"Entrypoint {value} must be a relative path")
        return value

    @field_validator("build_image", mode="before")
    @classmethod
    def _resolve_paths(cls, value: str, info: pydantic.ValidationInfo) -> Path:
        cwd = Path((info.context or {}).get("cwd", "."))
        return cwd / value


class PackageConfig(BaseModel):
    """The description of a package"""

    name: str = Field(description="Package name")
    version: str = Field(description="Package version")
    src: GitConfig | FileConfig | None = Field(
        None, discriminator="type", description="Source setup"
    )
    depends: list[str] = Field(default_factory=list, description="List of dependencies")

    build: str = Field(
        description="Build script, to be executed as a bash script inside of a container"
    )


class GitConfig(BaseModel):
    """Sets up a git-based source"""

    type: Literal["git"]
    url: str = Field(description="URL to the git repo")
    ref: str = Field(description="Commit reference (often a commit hash)")
    ssh_key_path: Annotated[
        Path | None,
        Field(
            exclude=True,
            description="Path to SSH key for cloning non-public repositories",
        ),
    ] = None


class FileConfig(BaseModel):
    """Sets up an individual local file as source"""

    type: Literal["file"]
    path: Path = Field(description="Path to file, relative to config file")
    fullpath: Annotated[
        Path | None, Field(exclude=True, description="Absolute path to file (internal)")
    ] = None

    @model_validator(mode="before")
    @classmethod
    def _resolve_paths(
        cls, data: dict[str, Any], info: pydantic.ValidationInfo
    ) -> dict[str, Any]:
        cwd = Path((info.context or {}).get("cwd", "."))
        data["fullpath"] = cwd / data["path"]
        return data


class AreaConfig(BaseModel):
    """TODO: AreaConfig"""

    name: str = Field(description="Display name")
    host: str = Field(description="Hostname or IP-address")


def load_config(path: Path) -> Config:
    with open(path) as f:
        return Config.model_validate(
            yaml.safe_load(f.read()), context={"cwd": path.absolute().parent}
        )
