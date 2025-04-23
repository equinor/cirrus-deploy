from __future__ import annotations


import asyncio
from pathlib import Path
from itertools import chain

from deploy.config import Config, AreaConfig


async def _ensure_dir(area: AreaConfig, path: Path) -> None:
    proc = await asyncio.create_subprocess_exec(
        "ssh", "-T", area.host, "--", "mkdir", "-p", path
    )
    await proc.wait()


async def _sync_area(area: AreaConfig, path: Path) -> None:
    await _ensure_dir(area, path)
    proc = await asyncio.create_subprocess_exec(
        "rsync",
        "-arv",
        "--info=progress2",
        f"{path}/",
        f"{area.host}:{path}/",
    )
    await proc.wait()



async def _sync(config: Config, prefix: Path) -> None:
    for path in chain([config.paths.store], (x.dest for x in config.envs)):
        tasks: list[asyncio.Task[None]] = []
        for area in config.areas:
            print(f"syncing path {prefix/str(path)} to {area.name}")
            task = asyncio.create_task(_sync_area(area, prefix / str(path)))
            await task



def do_sync(config: Config, *, prefix: Path) -> None:
    asyncio.run(_sync(config, prefix))
