from __future__ import annotations

import asyncio
import hashlib
import os
import subprocess
import sys
from contextlib import suppress
from datetime import datetime
from functools import cached_property
from pathlib import Path
from typing import Any
import networkx as nx

from deploy.config import BuildConfig, Config
from deploy.utils import redirect_output


class Package:
    def __init__(
        self,
        storepath: Path,
        cachepath: Path,
        config: BuildConfig,
        depends: list[Package],
    ) -> None:
        self.storepath = storepath
        self.cachepath = cachepath
        self.config = config
        self.depends = depends

    @property
    def fullname(self) -> str:
        return f"{self.config.name}-{self.config.version}"

    @property
    def out(self) -> Path:
        return self.storepath / f"{self.buildhash}-{self.fullname}"

    @property
    def src(self) -> Path:
        return self.cachepath / f"{self.config.name}-{self.config.git_ref}.git"

    @property
    def builder(self) -> Path:
        return Path(__file__).parent / f"scripts/build_{self.config.name}.sh"

    @cached_property
    def buildhash(self) -> str:
        h = hashlib.sha1(usedforsecurity=False)

        h.update(self.config.model_dump_json().encode("utf-8"))
        h.update(self.builder.read_bytes())

        for p in self.depends:
            h.update(p.buildhash.encode("utf-8"))

        return h.hexdigest()

    def checkout(self) -> None:
        try:
            self.src.mkdir(parents=True)
        except FileExistsError:
            return

        def git(*args: str | Path) -> None:
            subprocess.run(("git", *args), check=True, cwd=self.src)

        git("init", "--branch", "main")
        git("remote", "add", "origin", self.config.git_url)
        git("fetch", "origin", self.config.git_ref)
        git("checkout", "FETCH_HEAD")

    def build(self) -> None:
        try:
            self.out.mkdir()
        except FileExistsError:
            print(f"Ignoring {self.fullname}: Already built!", file=sys.stderr)
            return

        print(f"Building {self.fullname}...")
        self.checkout()

        env = {
            **os.environ,
            **{x.config.name: str(x.out) for x in self.depends},
            "src": str(self.src),
            "tmp": str(self.cachepath),
            "out": str(self.out),
        }
        with open(self.out / "build.log", "w") as buildlog:
            print("Built with https://github.com/equinor/cirrus-deploy", file=buildlog)
            print(f"Build date: {datetime.now()}", file=buildlog)
            print("----- BUILD CONFIG -----", file=buildlog)
            print(self.config.model_dump_json(), file=buildlog)
            print("------ BUILD  LOG ------", file=buildlog)

            asyncio.run(self._build(env, buildlog))

    async def _build(self, env: dict[str, str], buildlog: Any) -> None:
        proc = await asyncio.create_subprocess_exec(
            self.builder,
            cwd=self.src,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        await asyncio.gather(
            proc.wait(),
            redirect_output(self.config.name, proc.stdout, sys.stdout, buildlog),
            redirect_output(self.config.name, proc.stderr, sys.stderr, buildlog),
        )

    @cached_property
    def manifest(self) -> str:
        return "".join(sorted(f"{x.out}\n" for x in [*self.depends, self]))


class Build:
    def __init__(
        self, config: Config, *, system: bool = False, force: bool = False
    ) -> None:
        self.force = force
        self.base = config.paths.system_base if system else config.paths.local_base
        self.storepath = self.base / config.paths.store
        self.finalpath = self.base / config.paths.envs
        self.cachepath = Path("tmp").resolve()
        buildmap = {x.name: x for x in config.builds}

        graph: nx.DiGraph[str] = nx.DiGraph()
        for build in config.builds:
            for dep in build.depends:
                graph.add_edge(dep, build.name)

        self._packages: dict[str, Package] = {}
        for node in nx.topological_sort(graph):
            build = buildmap[node]
            self._packages[node] = Package(
                self.storepath,
                self.cachepath,
                build,
                [self._packages[x] for x in build.depends],
            )

    @property
    def final(self) -> Package:
        return self._packages["cirrus"]

    def build(self) -> None:
        self._build_packages()
        self._build_env()

    def _build_packages(self) -> None:
        for pkg in self._packages.values():
            pkg.build()

    def _build_env(self) -> None:
        path = (
            self.finalpath / f"{self.final.config.version}-{self._get_build_number()}"
        )

        for pkg in reversed(self._packages.values()):
            for srcdir, subdirs, files in os.walk(pkg.out):
                dstdir = path / srcdir[len(str(pkg.out)) + 1 :]
                dstdir.mkdir(exist_ok=True)
                for f in files:
                    with suppress(FileExistsError):
                        os.symlink(os.path.join(srcdir, f), os.path.join(dstdir, f))

        # Write a manifest file
        (path / "manifest").write_text(self.final.manifest)

    def _get_build_number(self) -> int:
        for i in range(1, 1000):
            path = self.finalpath / f"{self.final.config.version}-{i}"
            if not path.is_dir():
                return i

            if (
                not self.force
                and self.final.manifest == (path / "manifest").read_text()
            ):
                sys.exit(f"Environment already exists at {path}")

        sys.exit(
            f"Out of range while trying to find a build number for {self.final.config.version}"
        )
