from __future__ import annotations
from pathlib import Path
import sys
from typing import IO, Any, Self

from asyncio.subprocess import Process
from karsk.config import Config, load_config
from karsk.engine import (
    CpuArchNameNative,
    Engine,
    EngineNameNative,
    VolumeBind,
    get_engine,
)
from karsk.package import Package
from karsk.package_list import PackageList
from karsk.console import console
from karsk.paths import Paths


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
        self.staging_paths: Paths = Paths(staging, is_staging=True)
        self.target_paths: Paths = Paths(config.destination)
        self.plist: PackageList = PackageList(
            config,
            self.staging_paths,
            self.target_paths,
            check_existence=False,
        )
        self.engine: Engine = get_engine(engine, arch)
        self.engine_name: EngineNameNative | None = engine

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
            console.log(
                f"[yellow]The following packages haven't been built:[bold] {', '.join(missing)}"
            )
            console.log(
                "[yellow]Run '[bold]karsk build [CONFIG PATH][/bold]' to build all packages"
            )
            sys.exit(1)

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
            assert isinstance(package, str), (
                "if build is True, package kwarg must be a specific package to be built"
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

        return await self.engine(
            image,
            program,
            *args,
            volumes=volumes + self.plist.volumes(package),
            cwd=cwd,
            env=env,
            terminal=terminal,
            stdout=stdout,
            stderr=stderr,
        )
