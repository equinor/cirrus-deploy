from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Any
import networkx as nx
from itertools import chain
import shutil

from deploy.config import Config, GitConfig
from deploy.package import Package
from deploy.utils import redirect_output


def _checkout(pkg: Package) -> None:
    if not isinstance(gitconf := pkg.config.src, GitConfig) or pkg.src is None:
        return

    env = os.environ.copy()

    if gitconf.ssh_key_path is not None:
        env["GIT_SSH_COMMAND"] = (
            f"{os.environ.get('GIT_SSH_COMMAND', 'ssh')} -i {gitconf.ssh_key_path.absolute()}"
        )

    def git(*args: str | Path) -> None:
        subprocess.run(("git", *args), check=True, cwd=pkg.src, env=env)

    try:
        pkg.src.mkdir(parents=True)
    except FileExistsError:
        git("reset", "--hard")
        git("clean", "-xdf")
        return

    git("init", "-b", "main")
    git("remote", "add", "origin", gitconf.url)
    git("fetch", "origin", gitconf.ref)
    git("checkout", "FETCH_HEAD")


def _build(pkg: Package) -> None:
    try:
        pkg.out.mkdir()
    except FileExistsError:
        print(
            f"Ignoring {pkg.fullname}: Already built at {pkg.out}",
            file=sys.stderr,
        )
        return

    print(f"Building {pkg.fullname}...")
    try:
        _checkout(pkg)
    except BaseException:
        if pkg.src is not None:
            shutil.rmtree(pkg.src)
        shutil.rmtree(pkg.out)
        raise

    env = {
        **os.environ,
        **{x.config.name: str(x.out) for x in pkg.depends},
        "tmp": str(pkg.cachepath),
        "out": str(pkg.out),
    }

    if pkg.src is not None:
        env["src"] = str(pkg.src)

    with open(pkg.out / "build.log", "w") as buildlog:
        print("Built with https://github.com/equinor/cirrus-deploy", file=buildlog)
        print(f"Build date: {datetime.now()}", file=buildlog)
        print("----- BUILD CONFIG -----", file=buildlog)
        print(pkg.config.model_dump_json(), file=buildlog)
        print("------ BUILD  LOG ------", file=buildlog)

        try:
            asyncio.run(_async_build(pkg, env, buildlog))
        except BaseException as exc:
            for i in range(1000):
                fail_path = pkg.storepath / f"fail-{pkg.fullname}-{i}"
                if not fail_path.exists():
                    break
            else:
                sys.exit(f"Could not move failed build at {pkg.out}")

            pkg.out.rename(fail_path)
            sys.exit(
                f"Building {pkg.fullname} failed with exception {exc}. See failed build at: {fail_path}"
            )


async def _async_build(pkg: Package, env: dict[str, str], buildlog: Any) -> None:
    cwd = pkg.src if pkg.src is not None and pkg.src.is_dir() else Path("/tmp")

    proc = await asyncio.create_subprocess_exec(
        pkg.builder,
        cwd=cwd,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    await asyncio.gather(
        proc.wait(),
        redirect_output(pkg.config.name, proc.stdout, sys.stdout, buildlog),
        redirect_output(pkg.config.name, proc.stderr, sys.stderr, buildlog),
    )

    assert proc.returncode == 0


class Build:
    def __init__(
        self,
        configpath: Path,
        config: Config,
        *,
        prefix: Path,
        extra_scripts: Path | None = None,
        force: bool = False,
    ) -> None:
        self.force: bool = force
        self.prefix: Path = prefix
        self.storepath: Path = prefix / config.paths.store
        self.cachepath = (
            Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
            / "cirrus-deploy"
        )
        self.cachepath.mkdir(exist_ok=True, parents=True)
        buildmap = {x.name: x for x in config.builds}

        self.storepath.mkdir(parents=True, exist_ok=True)

        graph: nx.DiGraph[str] = nx.DiGraph()
        for build in config.builds:
            graph.add_node(build.name)
            for dep in build.depends:
                graph.add_edge(dep, build.name)

        self.packages: dict[str, Package] = {}
        for node in nx.topological_sort(graph):
            build = buildmap[node]
            self.packages[node] = Package(
                configpath,
                extra_scripts,
                self.storepath,
                self.cachepath,
                build,
                [self.packages[x] for x in build.depends],
            )

        self._envs: list[tuple[str, str]] = [(e.name, e.dest) for e in config.envs]

        self._check_scripts_exist()

    def _check_scripts_exist(self) -> None:
        for package in self.packages.values():
            if not package.builder.is_file() or not os.access(package.builder, os.X_OK):
                sys.exit(
                    f"Build script for package {package.config.name} ({package.builder.name}) wasn't found or it isn't executable"
                )

    def build(self) -> None:
        self._build_packages()
        self._build_envs()

    def _build_packages(self) -> None:
        for pkg in self.packages.values():
            _build(pkg)

    def _build_envs(self) -> None:
        for name, dest in self._envs:
            pkg = self.packages[name]
            path = self._get_build_path(self.prefix / dest, pkg)
            if path is None:
                continue
            self._build_env_for_package(path, pkg)

    def _build_env_for_package(self, base: Path, finalpkg: Package) -> None:
        for pkg in chain([finalpkg], finalpkg.depends):
            for srcdir, subdirs, files in os.walk(pkg.out):
                dstdir = base / srcdir[len(str(pkg.out)) + 1 :]
                dstdir.mkdir(parents=True, exist_ok=True)
                for f in files:
                    with suppress(FileExistsError):
                        os.symlink(os.path.join(srcdir, f), os.path.join(dstdir, f))

        # Write a manifest file
        (base / "manifest").write_text(finalpkg.manifest)

    def _get_build_path(self, base: Path, finalpkg: Package) -> Path | None:
        for i in range(1, 1000):
            path = base / f"{finalpkg.config.version}-{i}"
            if not path.is_dir():
                return path

            try:
                manifest = (path / "manifest").read_text()
            except FileNotFoundError:
                manifest = ""

            if not self.force and finalpkg.manifest == manifest:
                print(f"Environment already exists at {path}", file=sys.stderr)
                return None

        sys.exit(
            f"Out of range while trying to find a build number for {finalpkg.config.version}"
        )
