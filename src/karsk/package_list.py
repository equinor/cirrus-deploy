from __future__ import annotations

from collections.abc import Iterator
from itertools import chain
from pathlib import Path
import networkx as nx

from karsk.config import Config
from karsk.package import Package


class PackageList:
    """An ordered collection of packages sorted in topological (build) order."""

    def __init__(self, packages: dict[str, Package]) -> None:
        self._packages = packages

    def __iter__(self) -> Iterator[Package]:
        return iter(self._packages.values())

    def __getitem__(self, key: str) -> Package:
        return self._packages[key]

    def __len__(self) -> int:
        return len(self._packages)

    def __contains__(self, key: str) -> bool:
        return key in self._packages

    def get(self, key: str) -> Package | None:
        return self._packages.get(key)

    def keys(self) -> Iterator[str]:
        return iter(self._packages.keys())

    def values(self) -> Iterator[Package]:
        return iter(self._packages.values())

    def __eq__(self, other: object) -> bool:
        if isinstance(other, PackageList):
            return self._packages == other._packages
        if isinstance(other, dict):
            return self._packages == other
        return NotImplemented


def create_packages(
    config: Config,
    *,
    staging_storepath: Path,
    final_storepath: Path,
    cache: Path,
) -> PackageList:
    buildmap = {x.name: x for x in config.packages}

    graph: nx.DiGraph[str] = nx.DiGraph()
    for package in config.packages:
        graph.add_node(package.name)
        for dep in package.depends:
            graph.add_edge(dep, package.name)

    transitive_depends: dict[Package, list[Package]] = {}
    packages: dict[str, Package] = {}
    for node in nx.topological_sort(graph):
        build = buildmap[node]

        direct_depends = [packages[x] for x in build.depends]
        node_depends = [
            *direct_depends,
            *chain.from_iterable(transitive_depends[x] for x in direct_depends),
        ]

        new_package = Package(
            staging_storepath,
            final_storepath,
            build,
            node_depends,
            config.build_image,
            cache,
        )
        transitive_depends[new_package] = node_depends
        packages[node] = new_package

    return PackageList(packages)
