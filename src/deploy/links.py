from __future__ import annotations

import os
import sys

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

        try:
            version = Version.parse(name)
        except ValueError:
            continue

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


def make_links(
    links: dict[str, str],
    prefix: Path,
) -> None:
    for source, target in links.items():
        path = prefix / source

        if target == "^":
            target = get_latest(prefix)

        path.unlink(missing_ok=True)
        path.symlink_to(target)
        print(f"Created symlink: {path} -> {target}")

    validate(prefix)
