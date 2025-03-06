from __future__ import annotations
import sys
import asyncio
from pathlib import Path

import yaml
from pydantic import BaseModel

from deploy.config import Config, AreaConfig


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

    print(f"Finished area {area.name}")

    return Collect.model_validate(yaml.safe_load(stdout))


async def _check(config: Config) -> None:
    tasks: list[asyncio.Task[Collect]] = []

    if not config.areas:
        sys.exit("No areas specified in config.yaml")

    for area in config.areas:
        task = asyncio.create_task(collect(config, area))
        tasks.append(task)

    collected: dict[str, Collect] = {}

    for area, info in zip(
        config.areas, await asyncio.gather(*tasks, return_exceptions=True)
    ):
        print(f"Processed {area.name}")
        if isinstance(info, BaseException):
            raise info

        collected[area.name] = info

    all_areas = set(collected)
    all_unused_store_paths = set()
    for c in collected.values():
        all_unused_store_paths.update(c.unused_store_paths)

    print("Unused store paths:")
    for path in sorted(all_unused_store_paths):
        which = {k for k, v in collected.items() if path in v.unused_store_paths}
        which_str = "" if which == all_areas else ", ".join(which)
        print(f"{path:<120} {which_str}")


def do_check(config: Config) -> None:
    asyncio.run(_check(config))
