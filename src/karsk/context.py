from __future__ import annotations
from pathlib import Path
import sys
from typing import IO, Any, Self

from asyncio.subprocess import Process
from karsk import KarskError
from karsk.config import Config, load_config
from karsk.engine import (
    CpuArchName,
    CpuArchNameNative,
    Engine,
    EngineNameNative,
    VolumeBind,
    get_engine,
)
from karsk.package import Package
from karsk.package_list import PackageList
from karsk.paths import Paths


TARGET_TRIPLETS: dict[CpuArchName, str] = {
    "amd64": "x86_64-unknown-linux",
    "arm64": "aarch64-unknown-linux",
}


def _append_volume_if_exists(
    volumes: list[VolumeBind], staging: Path, target: Path
) -> None:
    if staging.is_dir():
        volumes.append((staging, target, "ro"))


class Context:
    def __init__(
        self,
        config: Config,
        *,
        staging: Path,
        engine: EngineNameNative | None = None,
        arch: CpuArchNameNative = "native",
    ) -> None:
        self.config: Config = config
        self.engine: Engine = get_engine(engine, arch)

        if self.engine.name != "native":
            staging = staging / config.main_package / TARGET_TRIPLETS[self.engine.arch]

        self.staging_paths: Paths = Paths(staging, is_staging=True)
        self.target_paths: Paths = Paths(config.destination)
        self.plist: PackageList = PackageList(
            config,
            self.staging_paths,
            self.target_paths,
            check_existence=False,
        )

    @property
    def destination(self) -> Path:
        return self.config.destination

    @property
    def can_debug(self) -> bool:
        """Returns True is it's possible to enter an interactive shell for debugging purposes"""
        return sys.stdin.isatty()

    @property
    def packages(self) -> dict[str, Package]:
        return self.plist.packages

    def out(self, package: Package | str, *, staging: bool = True) -> Path:
        """Helper for obtaining the output path for a given package. Mainly for use in tests"""
        if isinstance(package, str):
            package = self.packages[package]
        paths = self.staging_paths if staging else self.target_paths
        return paths.out(package)

    def __getitem__(self, key: str) -> Package:
        return self.packages[key]

    @classmethod
    def from_config_file(
        cls,
        config: Path,
        *,
        staging: Path,
        engine: EngineNameNative | None = None,
        arch: CpuArchNameNative = "native",
    ) -> Self:
        config_ = load_config(config)
        return cls(config_, staging=staging, engine=engine, arch=arch)

    @classmethod
    def from_config(
        cls,
        data: dict[str, Any],
        *,
        cwd: Path,
        staging: Path,
        engine: EngineNameNative | None = None,
        arch: CpuArchNameNative = "native",
    ) -> Self:
        config_ = Config.model_validate(data, context={"cwd": cwd})
        return cls(config_, staging=staging, engine=engine, arch=arch)

    def ensure_built(self, packages: list[str] | None = None) -> None:
        """Ensure that packages are present in staging. If 'packages' arg is
        specified, only those packages will be checked. Otherwise every
        package is expected to exist."""

        if packages is None:
            packages = sorted(self.packages.keys())

        missing: list[str] = []
        for pname in packages:
            if (pkg := self.plist.packages.get(pname)) is None:
                raise ValueError(f"No package {pname} defined")

            if not self.staging_paths.out(pkg).is_dir():
                missing.append(pname)

        if missing:
            raise KarskError(
                f"The following packages haven't been built: {', '.join(missing)}. "
                "Run 'karsk build [CONFIG PATH]' to build all packages."
            )

    async def run(
        self,
        program: str | Path,
        *args: str | Path,
        package: str | list[str] | None = None,
        volumes: list[VolumeBind] | None = None,
        build: bool = False,
        cwd: str | Path | None = None,
        env: dict[str, str] | None = None,
        terminal: bool = False,
        network: bool = True,
        stdout: IO[Any] | int | None = None,
        stderr: IO[Any] | int | None = None,
    ) -> Process:
        image: Path

        if cwd is None:
            cwd = "/"
        if env is None:
            env = {}
        if volumes is None:
            volumes = []

        if build:
            if not isinstance(package, str):
                raise TypeError(
                    "When build=True, package must be a specific package name (str)"
                )
            image = self.config.build_image
            package = [package]

        else:
            image = self.config.build_image

            if package is None:
                package = sorted(self.plist.packages.keys())
            elif isinstance(package, str):
                package = [package]

            self.ensure_built(package)

        _append_volume_if_exists(volumes, self.staging_paths.bin, self.target_paths.bin)
        _append_volume_if_exists(
            volumes, self.staging_paths.versions, self.target_paths.versions
        )

        return await self.engine(
            image,
            program,
            *args,
            volumes=volumes + self.plist.volumes(package),
            cwd=cwd,
            env=env,
            terminal=terminal,
            network=network,
            stdout=stdout,
            stderr=stderr,
        )
