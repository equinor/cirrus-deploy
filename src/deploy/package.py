from __future__ import annotations

import os.path
import hashlib
from functools import cached_property, lru_cache
from pathlib import Path

from deploy.config import BuildConfig, FileConfig, GitConfig


SCRIPTS = Path(__file__).parent / "scripts"


@lru_cache
def get_cache_path() -> Path:
    path = Path(os.environ.get("XDG_CACHE_HOME", "~/.cache")).expanduser().resolve()
    path /= "cirrus-deploy"
    path.mkdir(exist_ok=True, parents=True)
    return path


class Package:
    def __init__(
        self,
        configpath: Path,
        extra_scripts: Path | None,
        storepath: Path,
        config: BuildConfig,
        depends: list[Package],
    ) -> None:
        self.configpath = configpath
        self.extra_scripts = extra_scripts
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

    @property
    def builder(self) -> Path:
        name = f"build_{self.config.name}.sh"
        if self.extra_scripts is not None and (self.extra_scripts / name).is_file():
            return self.extra_scripts / name
        else:
            return SCRIPTS / name

    @cached_property
    def buildhash(self) -> str:
        h = hashlib.sha1(usedforsecurity=False)

        h.update(self.config.model_dump_json().encode("utf-8"))
        h.update(self.builder.read_bytes())

        if isinstance(self.config.src, FileConfig) and self.src is not None:
            h.update(self.src.read_bytes())

        for p in self.depends:
            h.update(p.buildhash.encode("utf-8"))

        return h.hexdigest()

    @cached_property
    def manifest(self) -> str:
        return "".join(sorted(f"{x.out}\n" for x in [*self.depends, self]))
