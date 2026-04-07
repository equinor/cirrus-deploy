from __future__ import annotations

import hashlib
from functools import cached_property
from pathlib import Path

from karsk.config import PackageConfig, FileConfig, GitConfig


SCRIPTS = Path(__file__).parent / "scripts"


class Package:
    def __init__(
        self,
        storepath: Path,
        final_storepath: Path,
        config: PackageConfig,
        depends: list[Package],
        build_image: Path,
        cache: Path,
    ) -> None:
        self.storepath = storepath.absolute()
        self.final_storepath = final_storepath.absolute()
        self.config = config
        self.cache = cache
        self.depends = depends
        self.build_image: Path = build_image

    @property
    def fullname(self) -> str:
        return f"{self.config.name}-{self.config.version}"

    @property
    def out(self) -> Path:
        return self.storepath / f"{self.buildhash}-{self.fullname}"

    @property
    def final_out(self) -> Path:
        return self.final_storepath / f"{self.buildhash}-{self.fullname}"

    @property
    def src(self) -> Path | None:
        if self.config.src is None:
            return None
        elif isinstance(self.config.src, GitConfig):
            return self.cache / f"{self.config.name}-{self.config.src.ref}.git"
        elif isinstance(self.config.src, FileConfig):
            assert self.config.src.fullpath is not None
            return self.config.src.fullpath
        else:
            raise RuntimeError("Unknown self.config.src type")

    @cached_property
    def buildhash(self) -> str:
        h = hashlib.sha1(usedforsecurity=False)

        h.update(self.config.model_dump_json().encode("utf-8"))

        if isinstance(self.config.src, FileConfig) and self.src is not None:
            h.update(self.src.read_bytes())

        for p in self.depends:
            h.update(p.buildhash.encode("utf-8"))

        return h.hexdigest()

    @cached_property
    def manifest(self) -> str:
        return "".join(sorted(f"{x.out}\n" for x in [*self.depends, self]))
