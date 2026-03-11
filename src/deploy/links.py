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


def _get_auto_version_aliases(prefix: Path) -> dict[str, str]:
    versions: list[tuple[Version, str]] = []

    if not prefix.is_dir():
        return {}

    for name in os.listdir(prefix):
        if name[0] == ".":
            continue
        path = prefix / name
        if path.is_symlink():
            continue
        try:
            versions.append((Version.parse(name), name))
        except ValueError:
            continue

    minor_aliases: dict[tuple[int, int], tuple[Version, str]] = {}
    for version, name in versions:
        key = (version.major, version.minor)
        if key not in minor_aliases or version > minor_aliases[key][0]:
            minor_aliases[key] = (version, name)

    aliases: dict[str, str] = {}
    for (major, minor), (_, name) in minor_aliases.items():
        aliases[f"{major}.{minor}"] = name

    major_aliases: dict[int, tuple[int, str]] = {}
    for (major, minor), _ in minor_aliases.items():
        alias = f"{major}.{minor}"
        if major not in major_aliases or minor > major_aliases[major][0]:
            major_aliases[major] = (minor, alias)

    for major, (_, alias) in major_aliases.items():
        aliases[str(major)] = alias

    return aliases


def make_links(
    links: dict[str, str],
    prefix: Path,
) -> None:
    auto_aliases = _get_auto_version_aliases(prefix)
    merged = {**auto_aliases, **links}

    for source, target in merged.items():
        path = prefix / source

        if target == "^":
            target = get_latest(prefix)

        path.unlink(missing_ok=True)
        path.symlink_to(target)
        print(f"Created symlink: {path} -> {target}")

    validate(prefix)
