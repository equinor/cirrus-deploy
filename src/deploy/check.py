from __future__ import annotations
import asyncio
import os
from typing import Literal

import yaml
from pydantic import BaseModel, RootModel, Field

from deploy.config import Config, AreaConfig

COLLECTOR = b"""\
#!/usr/bin/env python3
import os
import json
import re


def gather_versions() -> None:
    print("versions:")
    base = "/prog/pflotran/versions"
    for name in os.listdir(base):
        if name[0] == ".":
            continue
        path = os.path.join(base, name)
        if os.path.islink(path):
            target = os.readlink(path)
            print("- type: link")
            print(f"  name: !!str {name}")
            print(f"  target: !!str {target}")
        elif os.path.isdir(path):
            print(f"- type: dir")
            print(f"  name: !!str {name}")
        else:
            print(f"- type: other")
            print(f"  name: !!str {name}")
            
            
def gather_store() -> None:
    print("store:")
    base = "/prog/pflotran/versions/.builds"
    for name in os.listdir(base):
        print(f"- !!str {name}")


def main() -> None:
    gather_versions()
    gather_store()


if __name__ == "__main__":
    main()
"""


class VersionsLinkType(BaseModel):
    type: Literal["link"]
    name: str
    target: str


class VersionsDirType(BaseModel):
    type: Literal["dir"]
    name: str


class VersionsOtherType(BaseModel):
    type: Literal["other"]
    name: str


class Collect(BaseModel):
    versions: list[VersionsLinkType | VersionsDirType | VersionsOtherType] | None = None
    store: list[str] | None = None


async def collect(area: AreaConfig) -> Collect:
    proc = await asyncio.create_subprocess_exec("ssh", "-T", area.host, "/usr/bin/env", "python3", stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await proc.communicate(COLLECTOR)

    print(f"Finished area {area.name}")

    return Collect.model_validate(yaml.safe_load(stdout))


async def _check(config: Config) -> None:
    tasks: list[asyncio.Task] = []

    for area in config.areas:
        task = asyncio.create_task(collect(area))
        tasks.append(task)

    for area, info in zip(config.areas, await asyncio.gather(*tasks, return_exceptions=True)):
        print(f"--- {area.name} ---")
        for d in info.versions:
            if isinstance(d, VersionsDirType):
                print(f"  # {d.name}")
            elif isinstance(d, VersionsLinkType):
                print(f"  - {d.name} -> {d.target}")


def do_check(config: Config) -> None:
    asyncio.run(_check(config))