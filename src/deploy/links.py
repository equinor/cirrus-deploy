from __future__ import annotations

import os
import sys

from deploy.config import Config
from pathlib import Path
from semver import Version


def get_latest(basepath: Path) -> str:
    latest: tuple[Version, str] | None = None

    for name in os.listdir(basepath):
        if name[0] == ".":
            continue

        path = basepath / name
        if path.is_symlink():
            continue

        version = Version.parse(name)
        if latest is None or version > latest[0]:
            latest = (version, name)

    assert latest is not None
    return latest[1]


def validate(base: Path) -> None:
    for name in os.listdir(base):
        if name[0] == ".":
            continue

        path = base / name
        if not path.is_symlink():
            continue

        target = path.resolve()
        if not target.is_dir():
            print(f"'{name}' links to '{target}' which doesn't exist!", file=sys.stderr)


def make_links(config: Config, *, system: bool) -> None:
    base = Path(config.paths.system_base if system else config.paths.local_base)
    base /= config.paths.envs

    for source, target in config.links.items():
        path = base / source
        if target == "^":
            target = get_latest(base)
        path.unlink(missing_ok=True)
        path.symlink_to(target)

    validate(base)
