from __future__ import annotations

import hashlib
from functools import cached_property, lru_cache
from pathlib import Path

from deploy.config import BuildConfig, FileConfig, GitConfig


SCRIPTS = Path(__file__).parent / "scripts"


@lru_cache
def get_cache_path() -> Path:
    path = Path("./output/cache").resolve()
    path.mkdir(exist_ok=True, parents=True)
    return path


class Package:
    def __init__(
        self,
        configpath: Path,
        storepath: Path,
        config: BuildConfig,
        depends: list[Package],
    ) -> None:
        self.configpath = configpath
        self.storepath = storepath
        self.config = config
        self.depends = depends

    @property
    def fullname(self) -> str:
        return f"{self.config.name}-{self.config.version}"

    @property
    def out(self) -> Path:
        return self.storepath / f"{self.buildhash}-{self.fullname}"

    @property
    def src(self) -> Path | None:
        if self.config.src is None:
            return None
        elif isinstance(self.config.src, GitConfig):
            return get_cache_path() / f"{self.config.name}-{self.config.src.ref}.git"
        elif isinstance(self.config.src, FileConfig):
            return self.configpath / self.config.src.path
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
