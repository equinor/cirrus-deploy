from __future__ import annotations

from itertools import chain
import sys
from pathlib import Path
import networkx as nx

from karsk.config import Config
from karsk.engine import VolumeBind
from karsk.package import Package


class PackageList:
    def __init__(
        self,
        config: Config,
        *,
        staging: Path,
        check_existence: bool = True,
    ) -> None:
        self.staging: Path = staging
        self.staging_storepath: Path = staging / Path(".store")
        self.storepath: Path = config.destination / ".store"
        self.config: Config = config
        buildmap = {x.name: x for x in config.packages}

        self.staging_storepath.mkdir(parents=True, exist_ok=True)

        graph: nx.DiGraph[str] = nx.DiGraph()
        for package in config.packages:
            graph.add_node(package.name)
            for dep in package.depends:
                graph.add_edge(dep, package.name)

        transitive_depends: dict[Package, list[Package]] = {}
        self.packages: dict[str, Package] = {}
        for node in nx.topological_sort(graph):
            build = buildmap[node]

            direct_depends = [self.packages[x] for x in build.depends]
            node_depends = [
                *direct_depends,
                *chain.from_iterable(transitive_depends[x] for x in direct_depends),
            ]

            new_package = Package(
                self.staging_storepath,
                self.storepath,
                build,
                node_depends,
                config.build_image,
                staging / "cache",
            )
            transitive_depends[new_package] = node_depends
            self.packages[node] = new_package

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
