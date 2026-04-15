from __future__ import annotations
from pathlib import Path
from typing import IO, Any, Self

from asyncio.subprocess import Process
from karsk.config import Config, load_config
from karsk.engine import Engine, EngineName, VolumeBind, get_engine
from karsk.package import Package
from karsk.package_list import PackageList, create_packages
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
        self._staging: Path = staging.absolute()
        self.engine: Engine = get_engine(engine)
        self.engine_name: EngineName | None = engine

        staging_storepath = self._staging / ".store"
        staging_storepath.mkdir(parents=True, exist_ok=True)

        self.packages: PackageList = create_packages(
            config,
            staging_storepath=staging_storepath,
            final_storepath=config.destination / ".store",
            cache=self._staging / "cache",
        )

    @property
    def destination(self) -> Path:
        return self.config.destination

    @property
    def staging(self) -> Path:
        return self._staging

    def __getitem__(self, key: str) -> Package:
        return self.packages[key]

    def volumes(self, package_names: list[str]) -> list[VolumeBind]:
        pnames = set(package_names)
        for pname in package_names:
            pkg = self.packages[pname]
            pnames |= set(p.config.name for p in pkg.depends)

        return [
            (pkg.out, pkg.final_out, "ro")
            for pkg in (self.packages[pname] for pname in pnames)
        ]

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
                package = sorted(self.packages.keys())
            elif isinstance(package, str):
                package = [package]

            missing: list[str] = []
            for pname in package:
                if (pkg := self.packages.get(pname)) is None:
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
            volumes=volumes + self.volumes(package),
            cwd=cwd,
            env=env,
            terminal=terminal,
            stdout=stdout,
            stderr=stderr,
        )
