from __future__ import annotations
from pathlib import Path
import sys
from typing import IO, Any, Self

from asyncio.subprocess import Process
from karsk.config import Config, load_config
from karsk.engine import Engine, EngineName, VolumeBind, get_engine
from karsk.package import Package
from karsk.package_list import PackageList
from karsk.console import console


class Context:
    def __init__(
        self,
        config: Config,
        *,
        staging: Path,
        engine: EngineName | None = None,
    ) -> None:
        self.config: Config = config
        self.plist: PackageList = PackageList(
            config,
            staging=staging.absolute(),
            check_existence=False,
        )
        self.engine: Engine = get_engine(engine)
        self.engine_name: EngineName | None = engine

    @property
    def can_debug(self) -> bool:
        """Returns True is it's possible to enter an interactive shell for debugging purposes"""
        return sys.stdin.isatty()

    @property
    def destination(self) -> Path:
        return self.config.destination

    @property
    def staging(self) -> Path:
        return self.plist.staging

    @property
    def packages(self) -> dict[str, Package]:
        return self.plist.packages

    def __getitem__(self, key: str) -> Package:
        return self.packages[key]

    @classmethod
    def from_config_file(
        cls,
        config: Path,
        *,
        staging: Path,
        engine: EngineName | None = None,
    ) -> Self:
        config_ = load_config(config)
        return cls(config_, staging=staging, engine=engine)

    @classmethod
    def from_config(
        cls,
        data: dict[str, Any],
        *,
        cwd: Path,
        staging: Path,
        engine: EngineName | None = None,
    ) -> Self:
        config_ = Config.model_validate(data, context={"cwd": cwd})
        return cls(config_, staging=staging, engine=engine)

    async def run(
        self,
        program: str,
        *args: str,
        package: str | list[str] | None = None,
        volumes: list[VolumeBind] | None = None,
        build: bool = False,
        cwd: str | Path | None = None,
        env: dict[str, str] | None = None,
        terminal: bool = False,
        stdout: IO[Any] | None = None,
        stderr: IO[Any] | None = None,
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

            missing: list[str] = []
            for pname in package:
                if (pkg := self.plist.packages.get(pname)) is None:
                    raise ValueError(f"No package {pname} defined")

                if not pkg.is_built:
                    missing.append(pname)

            if missing:
                console.log(
                    f"[yellow]The following packages haven't been built:[bold] {', '.join(missing)}"
                )
                console.log(
                    "[yellow]Run '[bold]karsk build [CONFIG PATH][/bold]' to build all packages"
                )

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
