from __future__ import annotations
import sys
import asyncio
from pathlib import Path
from typing import Awaitable, Coroutine, Iterable, TypeVar

import yaml
from pydantic import BaseModel

from deploy.config import Config, AreaConfig
from rich.console import Console
from rich.progress import Progress
from rich.table import Table


console = Console()


class Collect(BaseModel):
    unused_store_paths: set[str]


SCRIPT: bytes = (Path(__file__).parent / "_check.py").read_bytes()


async def collect(config: Config, area: AreaConfig) -> Collect:
    base = Path(config.paths.system_base)
    store = base / config.paths.store
    versions = [base / env.dest for env in config.envs]

    proc = await asyncio.create_subprocess_exec(
        "ssh",
        "-T",
        area.host,
        "/usr/bin/python3.6",
        "-",
        "--store",
        store,
        "--versions",
        *versions,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate(SCRIPT)

    console.log(f"Finished area {area.name}")

    return Collect.model_validate(yaml.safe_load(stdout))


_T = TypeVar("_T")


async def _pretty_gather(*coros: Awaitable[_T]) -> list[_T]:
    tasks: list[asyncio.Task[_T]] = []
    with Progress(console=console) as progress:
        progress_task = progress.add_task("[cyan]Checking...", total=len(coros))

        for coro in coros:
            task = asyncio.create_task(coro)
            task.add_done_callback(lambda *_: progress.advance(progress_task))
            tasks.append(task)

        return await asyncio.gather(*tasks)


async def _check(config: Config) -> None:
    if not config.areas:
        sys.exit("No areas specified in config.yaml")

    results = await _pretty_gather(
        *(collect(config, area) for area in config.areas)
    )
    collected = {
        area.name: info
        for area, info in zip(config.areas, results)
    }

    all_areas = set(collected)
    all_unused_store_paths: set[str] = set()
    for c in collected.values():
        all_unused_store_paths.update(c.unused_store_paths)


    table = Table(title="Unused store paths")
    table.add_column("Path", no_wrap=True)
    table.add_column("Area(s)")

    for path in sorted(all_unused_store_paths):
        which = {k for k, v in collected.items() if path in v.unused_store_paths}
        which_str = "All" if which == all_areas else ", ".join(which)

        table.add_row(path, which_str)

    console.print(table)


def do_check(config: Config) -> None:
    asyncio.run(_check(config))
