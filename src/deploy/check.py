from __future__ import annotations
import asyncio
import os
from typing import Literal

import yaml
from pydantic import BaseModel, RootModel, Field

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


async def collect(hostname: str) -> None:
    proc = await asyncio.create_subprocess_exec("ssh", "-T", hostname, "/usr/bin/env", "python3", stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await proc.communicate(COLLECTOR)

    os.write(1, stdout)

    print(yaml.safe_load(stdout))

    print(Collect.model_validate(yaml.safe_load(stdout)))


if __name__ == "__main__":
    asyncio.run(collect("be-grid01.be.statoil.no"))