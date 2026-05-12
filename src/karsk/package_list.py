from __future__ import annotations

import hashlib
from itertools import chain
import sys
import networkx as nx

from karsk.config import Config
from karsk.engine import VolumeBind
from karsk.package import Package
from karsk.paths import Paths


class PackageList:
    def __init__(
        self,
        config: Config,
        staging_paths: Paths,
        target_paths: Paths,
        *,
        check_existence: bool = True,
    ) -> None:
        self.staging_paths: Paths = staging_paths
        self.target_paths: Paths = target_paths
        self.config: Config = config
        buildmap = {x.name: x for x in config.packages}

        self.staging_paths.store.mkdir(parents=True, exist_ok=True)

        graph: nx.DiGraph[str] = nx.DiGraph()
        for package in config.packages:
            graph.add_node(package.name)
            for dep in package.depends:
                graph.add_edge(dep, package.name)

        initial_hash = self._initial_hash()
        transitive_depends: dict[Package, list[Package]] = {}
        self.packages: dict[str, Package] = {}
        for node in nx.topological_sort(graph):
            package_config = buildmap[node]

            direct_depends = [self.packages[x] for x in package_config.depends]
            node_depends = [
                *direct_depends,
                *chain.from_iterable(transitive_depends[x] for x in direct_depends),
            ]

            new_package = Package(
                package_config,
                node_depends,
                config.build_image,
                initial_hash,
            )
            transitive_depends[new_package] = node_depends
            self.packages[node] = new_package

        if check_existence:
            self._check_existence()

    def _initial_hash(self) -> bytes:
        h = hashlib.sha1(usedforsecurity=False)

        h.update(self.config.destination.as_posix().encode())
        h.update(self.config.build_image.read_bytes())

        return h.digest()

    def volumes(self, package_names: list[str]) -> list[VolumeBind]:
        pnames = set(package_names)
        for pname in package_names:
            pkg = self.packages[pname]
            pnames |= set(p.config.name for p in pkg.depends)

        return [
            (self.staging_paths.out(pkg), self.target_paths.out(pkg), "ro")
            for pkg in (self.packages[pname] for pname in pnames)
        ]

    def _check_existence(self) -> None:
        for pkg in self.packages.values():
            out = self.staging_paths.out(pkg)
            if not out.is_dir():
                sys.exit(
                    f"{out} doesn't exist. Are you sure that '{pkg.fullname}' is installed?"
                )
