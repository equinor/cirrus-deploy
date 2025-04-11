from __future__ import annotations


import sys
import asyncio
from pathlib import Path

from deploy.config import Config, AreaConfig
from deploy.package_list import PackageList
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


async def _sync(configpath: Path, config: Config, prefix: Path) -> None:
    plist = PackageList(configpath, config, prefix=prefix)

    # Copy over store locations
    for pkg in plist.packages.values():
        tasks: list[asyncio.Task[None]] = []
        for area in config.areas:
            task = asyncio.create_task(_sync_area(area, pkg.out))
            tasks.append(task)

        await asyncio.gather(*tasks)


def do_sync(configpath: Path, config: Config, *, prefix: Path) -> None:
    asyncio.run(_sync(configpath, config, prefix))
