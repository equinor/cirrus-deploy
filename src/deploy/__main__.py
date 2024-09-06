from __future__ import annotations
import asyncio
from pathlib import Path
import typer
import socket


AREAS = [
    "be-grid01.be.statoil.no",
    "st-grid01.st.statoil.no",
    "s268-lckm.s268.oc.equinor.com",  # master node of CCS CycleCloud
    "tr-grid01.tr.statoil.no",
    "hou-grid01.hou.statoil.no",
    # "rio-grid01.rio.statoil.no",  # I have no home directory ~Zohar
    "stjohn-grid01.stjohn.statoil.no",
]


async def exec_proc(label: str, program: str | Path, *args: str | Path) -> asyncio.subprocess.Process:
    proc = await asyncio.create_subprocess_exec(program, *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, stdin=asyncio.subprocess.DEVNULL)


async def rsync(area: str, path: Path) -> None:
    proc = await asyncio.create_subprocess_exec(
        "rsync",
        "-ar",
        "--info=progress2",
        f"{path}/",
        f"{area}:{path}/",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )


async def amain() -> None:
    pass


def _main() -> None:
    asyncio.run(amain())


def main() -> None:
    typer.run(_main)


if __name__ == "__main__":
    main()
