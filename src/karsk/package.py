from __future__ import annotations

import hashlib
from functools import cached_property
from pathlib import Path

from karsk.config import ArchiveConfig, PackageConfig, FileConfig, GitConfig


SCRIPTS = Path(__file__).parent / "scripts"


class Package:
    def __init__(
        self,
        config: PackageConfig,
        depends: list[Package],
        build_image: Path,
    ) -> None:
        self.config = config
        self.depends = depends
        self.build_image: Path = build_image

    @property
    def fullname(self) -> str:
        return f"{self.config.name}-{self.config.version}"

    @property
    def out_relpath(self) -> Path:
        """Path for the output directory relative to 'store'"""
        return Path(f"{self.buildhash}-{self.fullname}")

    @property
    def src_relpath(self) -> Path | None:
        """Path for the input directory relative to 'cache'"""
        if self.config.src is None:
            return None
        elif isinstance(self.config.src, GitConfig):
            return Path(f"{self.config.name}-{self.config.src.ref}.git")
        elif isinstance(self.config.src, ArchiveConfig):
            return Path(f"{self.config.name}-{self.config.version}")
        elif isinstance(self.config.src, FileConfig):
            assert self.config.src.fullpath is not None
            return self.config.src.fullpath
        else:
            raise RuntimeError("Unknown self.config.src type")

    @cached_property
    def buildhash(self) -> str:
        h = hashlib.sha1(usedforsecurity=False)

        h.update(self.config.model_dump_json().encode("utf-8"))

        if (
            isinstance(self.config.src, FileConfig)
            and self.src_relpath is not None
            and self.src_relpath.is_absolute()
        ):
            h.update(self.src_relpath.read_bytes())

        for p in self.depends:
            h.update(p.buildhash.encode("utf-8"))

        return h.hexdigest()

    @cached_property
    def manifest(self) -> str:
        return "".join(sorted(f"{x.out_relpath}\n" for x in [*self.depends, self]))
