from __future__ import annotations


import sys
import asyncio
from pathlib import Path
from itertools import chain

from deploy.config import Config, AreaConfig
from deploy.utils import redirect_output


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
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    await asyncio.gather(
        proc.wait(),
        redirect_output(area.name, proc.stdout, sys.stdout),
        redirect_output(area.name, proc.stderr, sys.stderr),
    )


async def _sync(config: Config, system: bool) -> None:
    base = Path(config.paths.system_base if system else config.paths.local_base)

    for path in chain([config.paths.store], (x.dest for x in config.envs)):
        tasks: list[asyncio.Task[None]] = []
        for area in config.areas:
            task = asyncio.create_task(_sync_area(area, base / Path(str(path))))
            tasks.append(task)

        await asyncio.gather(*tasks)


def do_sync(config: Config, *, system: bool) -> None:
    asyncio.run(_sync(config, system))
