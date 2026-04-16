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


class Config(BaseModel):
    """Main configuration model"""

    model_config = ConfigDict(
        alias_generator=(lambda x: x.replace("_", "-")), extra="forbid"
    )

    destination: Path = Field(
        description="Absolute path to deployment area to be managed by Karsk (eg: '/opt/karsk')"
    )
    main_package: str = Field(description="Name of primary package (eg: 'hello')")
    entrypoints: list[str] = Field(
        description="List of executable names to expose in bin/ directory",
        examples=["['hello']"],
    )
    build_image: FilePath = Field(
        description="Path to containerfile to use for building (eg: './Containerfile')"
    )

    tests: Path | None = Field(
        None, description="Path to directory containing pytest-based tests"
    )

    packages: list[PackageConfig] = Field(description="List of packages to build")
    links: dict[str, str] = Field(
        default_factory=dict, description="Symbolic links setup"
    )

    @field_validator("destination")
    @classmethod
    def validate_is_absolute_path(cls, value: Path) -> Path:
        if not value.is_absolute():
            raise ValueError(f"{value} must be an absolute path")
        return value

    @field_validator("entrypoints")
    @classmethod
    def validate_is_not_a_path(cls, value: list[str]) -> list[str]:
        for v in value:
            if "/" in v:
                raise ValueError(
                    f"{v} must be a file name and not a path (cannot contain '/')"
                )
        return value

    @field_validator("build_image", "tests", mode="before")
    @classmethod
    def _resolve_paths(
        cls, value: str | None, info: pydantic.ValidationInfo
    ) -> Path | None:
        if value is None:
            return None

        cwd = Path((info.context or {}).get("cwd", "."))
        return cwd / value


class PackageConfig(BaseModel):
    """The description of a package"""

    name: str = Field(description="Package name")
    version: str = Field(description="Package version")
    src: GitConfig | FileConfig | ArchiveConfig | None = Field(
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


class ArchiveConfig(BaseModel):
    """Download and extract an archive (currently a tarball) from a URL"""

    type: Literal["archive"]
    url: str = Field(description="URL to the archive")


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
    name: str = Field(description="Display name")
    host: str = Field(description="Hostname or IP-address")


def load_config(path: Path) -> Config:
    with open(path) as f:
        return Config.model_validate(
            yaml.safe_load(f.read()), context={"cwd": path.absolute().parent}
        )


def load_areas(path: Path) -> list[AreaConfig]:
    with open(path) as f:
        data = yaml.safe_load(f.read())
    return [AreaConfig.model_validate(item) for item in data["areas"]]
