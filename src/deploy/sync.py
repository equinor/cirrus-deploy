from __future__ import annotations

import sys
import asyncio
from pathlib import Path

from deploy.config import Config, AreaConfig


async def _tee(stream: asyncio.StreamReader, name: str, io) -> None:
    while not stream.at_eof():
        try:
            while True:
                line = await stream.readuntil()
                print(f"{name}> {line.decode('utf-8', errors='replace')[:-1]}", file=io)
        except asyncio.IncompleteReadError:
            await asyncio.sleep(0.5)


async def _ensure_dir(area: AreaConfig, path: Path) -> None:
    proc = await asyncio.create_subprocess_exec("ssh", "-T", area.host, "--", "mkdir", "-p", path)
    await proc.wait()


async def _sync_area(area: AreaConfig, path: Path) -> None:
    await _ensure_dir(area, path)
    proc = await asyncio.create_subprocess_exec("rsync", "-arv", "--info=progress2", f"{path}/", f"{area.host}:{path}/", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)

    await asyncio.gather(
        proc.wait(),
        _tee(proc.stdout, area.name, sys.stdout),
        _tee(proc.stderr, area.name, sys.stderr),
    )


async def _sync(config: Config) -> None:
    base = config.paths.local_base
    store = base / config.paths.store

    tasks: list[asyncio.Task] = []
    for area in config.areas:
        task = asyncio.create_task(_sync_area(area, store))
        tasks.append(task)

    await asyncio.gather(*tasks)


def do_sync(config: Config) -> None:
    asyncio.run(_sync(config))