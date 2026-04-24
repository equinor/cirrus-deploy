from __future__ import annotations

import os
import sys

from pathlib import Path
from semver import Version


def _version_key(version: Version) -> tuple[int, int, int, str, int]:
    """Sortable key that includes build metadata, which semver ignores by default."""
    return (
        version.major,
        version.minor,
        version.patch,
        version.prerelease or "",
        int(version.build) if version.build else 0,
    )


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

        if latest is None or _version_key(version) > _version_key(latest[0]):
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


def _reduce_aliases(
    entries: dict[tuple[int, ...], str],
    aliases: dict[str, str],
) -> None:
    if not entries or len(next(iter(entries))) <= 1:
        return

    best: dict[tuple[int, ...], tuple[int, str]] = {}
    for key, target in entries.items():
        group = key[:-1]
        last = key[-1]
        if group not in best or last > best[group][0]:
            best[group] = (last, target)

    next_entries: dict[tuple[int, ...], str] = {}
    for group, (_, target) in best.items():
        alias_key = ".".join(str(x) for x in group)
        aliases[alias_key] = target
        next_entries[group] = alias_key

    _reduce_aliases(next_entries, aliases)


def _get_auto_version_aliases(destination: Path) -> dict[str, str]:
    if not destination.is_dir():
        return {}

    entries: dict[tuple[int, ...], str] = {}
    for name in os.listdir(destination):
        if name[0] == ".":
            continue
        if (destination / name).is_symlink():
            continue
        try:
            version = Version.parse(name)
        except ValueError:
            continue
        build = int(version.build) if version.build else 0
        entries[(version.major, version.minor, version.patch, build)] = name

    aliases: dict[str, str] = {}
    _reduce_aliases(entries, aliases)

    return aliases


def make_links(
    links: dict[str, str],
    destination: Path,
) -> None:
    auto_aliases = _get_auto_version_aliases(destination)
    merged = {**auto_aliases, **links}

    for source, target in merged.items():
        path = destination / source

        if target == "^":
            target = get_latest(destination)

        path.unlink(missing_ok=True)
        path.symlink_to(target)
        print(f"Created symlink: {path} -> {target}")

    validate(destination)
