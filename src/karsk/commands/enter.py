from __future__ import annotations

import asyncio
from typing import Literal

from pathlib import Path
import shlex
import sys

import click

from karsk.commands._common import (
    argument_config_file,
    option_arch,
    option_staging,
    option_engine,
)
from karsk.context import Context
from karsk.engine import CpuArchNameNative, VolumeBind
from karsk.console import console
from karsk.engine import EngineNameNative


KARSK_BASHRC = Path(__file__).parent / "../data/enter.bashrc"


class VolumeBindType(click.ParamType):
    name = "volume"

    def convert(
        self, value: str, param: click.Parameter | None, ctx: click.Context | None
    ) -> VolumeBind:

        parts = value.split(":")
        if len(parts) not in (2, 3):
            self.fail(
                "Volume must be in the form /src/path:/dst/path[:ro|rw]",
                param,
                ctx,
            )

        src_str, dst_str = parts[:2]
        mode: Literal["ro", "rw"] = parts[2] if len(parts) == 3 else "rw"  # type: ignore[assignment]

        if mode not in ("ro", "rw"):
            self.fail("Mode must be 'ro' or 'rw'", param, ctx)

        src = Path(src_str)
        if not src.exists():
            self.fail(f"Source must be an existing path:{src}", param, ctx)

        dst = Path(dst_str)
        result: VolumeBind = (src.absolute(), dst, mode)

        return result


async def _main(ctx: Context, *args: str, volumes: tuple[VolumeBind, ...]) -> None:
    cwd = Path.cwd()
    home = Path.home()

    # If current working directory is not inside of home, default to a safe
    # location
    if not cwd.is_relative_to(home):
        cwd = Path("/")

    console.log(f"Entering Karsk environment using command: [blue]{shlex.join(args)}")
    proc = await ctx.run(
        *args,
        volumes=[
            (KARSK_BASHRC, "/etc/karsk.bashrc", "ro"),
            (ctx.staging_paths.bin, ctx.target_paths.bin, "ro"),
            (ctx.staging_paths.versions, ctx.target_paths.versions, "ro"),
            (home, home, "rw"),
            *volumes,
        ],
        env={"KARSK_PATH": str(ctx.target_paths.bin)},
        cwd=cwd,
        terminal=True,
    )
    sys.exit(await proc.wait())


VOLUME_BIND = VolumeBindType()


@click.command("enter", help="Enter environment")
@argument_config_file
@click.argument("args", nargs=-1)
@option_staging
@option_engine
@option_arch
@click.option("-v", "--volume", multiple=True, type=VOLUME_BIND)
def subcommand_enter(
    config_file: Path,
    staging: Path,
    args: tuple[str, ...],
    engine: EngineNameNative | None,
    arch: CpuArchNameNative,
    volume: tuple[VolumeBind, ...],
) -> None:
    if args == ():
        args = ("bash", "--rcfile", "/etc/karsk.bashrc")

    ctx = Context.from_config_file(
        config_file, staging=staging, engine=engine, arch=arch
    )
    console.log("Destination path:", ctx.destination)
    asyncio.run(_main(ctx, *args, volumes=volume))
