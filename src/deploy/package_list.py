from __future__ import annotations

import sys
from pathlib import Path
import networkx as nx

from deploy.config import Config
from deploy.engine import VolumeBind
from deploy.package import Package


class PackageList:
    def __init__(
        self,
        config: Config,
        *,
        prefix: Path,
        output: Path,
        check_existence: bool = True,
    ) -> None:
        self.prefix: Path = prefix
        self.storepath: Path = output / Path(".store")
        self.final_storepath: Path = prefix / ".store"
        self.config: Config = config
        buildmap = {x.name: x for x in config.packages}

        self.storepath.mkdir(parents=True, exist_ok=True)

        graph: nx.DiGraph[str] = nx.DiGraph()
        for package in config.packages:
            graph.add_node(package.name)
            for dep in package.depends:
                graph.add_edge(dep, package.name)

        self.packages: dict[str, Package] = {}
        for node in nx.topological_sort(graph):
            build = buildmap[node]
            self.packages[node] = Package(
                self.storepath,
                self.final_storepath,
                build,
                [self.packages[x] for x in build.depends],
                build.build_image or config.build_image,
                output / "cache",
            )

        if check_existence:
            self._check_existence()

    def volumes(self, package_names: list[str]) -> list[VolumeBind]:
        pnames = set(package_names)
        for pname in package_names:
            pkg = self.packages[pname]
            pnames |= set(p.config.name for p in pkg.depends)

        return [
            (pkg.out, pkg.final_out, "ro")
            for pkg in (self.packages[pname] for pname in pnames)
        ]

    def _check_existence(self) -> None:
        for pkg in self.packages.values():
            if not pkg.out.is_dir():
                sys.exit(
                    f"{pkg.out} doesn't exist. Are you sure that '{pkg.fullname}' is installed?"
                )
