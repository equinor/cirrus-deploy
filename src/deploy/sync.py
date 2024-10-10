from __future__ import annotations


import sys
import asyncio
from pathlib import Path

from deploy.config import Config, AreaConfig
from deploy.utils import redirect_output


async def _ensure_dir(area: AreaConfig, path: Path) -> None:
    proc = await asyncio.create_subprocess_exec("ssh", "-T", area.host, "--", "mkdir", "-p", path)
    await proc.wait()


async def _sync_area(area: AreaConfig, path: Path) -> None:
    await _ensure_dir(area, path)
    proc = await asyncio.create_subprocess_exec("rsync", "-arv", "--info=progress2", f"{path}/", f"{area.host}:{path}/", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)

    await asyncio.gather(
        proc.wait(),
        redirect_output(area.name, proc.stdout, sys.stdout),
        redirect_output(area.name, proc.stderr, sys.stderr),
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
