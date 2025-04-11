from __future__ import annotations

import os
import sys
from pathlib import Path
import networkx as nx

from deploy.config import Config
from deploy.package import Package


class PackageList:
    def __init__(
        self,
        configpath: Path,
        config: Config,
        *,
        prefix: Path,
        extra_scripts: Path | None = None,
        check_scripts: bool = False,
        check_existence: bool = True,
    ) -> None:
        self.prefix: Path = prefix
        self.storepath: Path = prefix / config.paths.store
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
                build,
                [self.packages[x] for x in build.depends],
            )

        self.envs: list[tuple[str, str]] = [(e.name, e.dest) for e in config.envs]

        if check_scripts:
            self._check_scripts_exist()
        if check_existence:
            self._check_existence()

    def _check_scripts_exist(self) -> None:
        for package in self.packages.values():
            if not package.builder.is_file() or not os.access(package.builder, os.X_OK):
                sys.exit(
                    f"Build script for package {package.config.name} ({package.builder.name}) wasn't found or it isn't executable"
                )

    def _check_existence(self) -> None:
        for pkg in self.packages.values():
            if not pkg.out.is_dir():
                sys.exit(
                    f"{pkg.out} doesn't exist. Are you sure that '{pkg.fullname}' is installed?"
                )
