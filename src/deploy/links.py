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
    if not prefix.is_dir():
        return {}

    versions: list[tuple[Version, str]] = []
    for name in os.listdir(prefix):
        if name[0] == ".":
            continue
        if (prefix / name).is_symlink():
            continue
        try:
            versions.append((Version.parse(name), name))
        except ValueError:
            continue

    aliases: dict[str, str] = {}

    patch_best: dict[tuple[int, int, int], tuple[Version, str]] = {}
    for version, name in versions:
        key = (version.major, version.minor, version.patch)
        if key not in patch_best or version > patch_best[key][0]:
            patch_best[key] = (version, name)

    for (major, minor, patch), (_, name) in patch_best.items():
        aliases[f"{major}.{minor}.{patch}"] = name

    minor_best: dict[tuple[int, int], tuple[int, str]] = {}
    for (major, minor, patch), _ in patch_best.items():
        alias = f"{major}.{minor}.{patch}"
        if (major, minor) not in minor_best or patch > minor_best[(major, minor)][0]:
            minor_best[(major, minor)] = (patch, alias)

    for (major, minor), (_, alias) in minor_best.items():
        aliases[f"{major}.{minor}"] = alias

    major_best: dict[int, tuple[int, str]] = {}
    for (major, minor), _ in minor_best.items():
        alias = f"{major}.{minor}"
        if major not in major_best or minor > major_best[major][0]:
            major_best[major] = (minor, alias)

    for major, (_, alias) in major_best.items():
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
