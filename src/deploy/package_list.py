from __future__ import annotations

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
                self.storepath,
                build,
                [self.packages[x] for x in build.depends],
            )

        self.envs: list[tuple[str, str, str | None]] = [
            (e.name, e.dest, e.entrypoint) for e in config.envs
        ]

        if check_existence:
            self._check_existence()

    def _check_existence(self) -> None:
        for pkg in self.packages.values():
            if not pkg.out.is_dir():
                sys.exit(
                    f"{pkg.out} doesn't exist. Are you sure that '{pkg.fullname}' is installed?"
                )
