from __future__ import annotations

import asyncio
from pathlib import Path
import shlex
import sys

import click

from karsk.commands._common import argument_config_file, option_staging, option_prefix
from karsk.context import Context
from karsk.console import console


async def _main(ctx: Context, *args: str) -> None:
    cwd = Path.cwd()
    home = Path.home()

    # If current working directory is not inside of home, default to a safe
    # location
    if not cwd.is_relative_to(home):
        cwd = Path("/")

    console.log(f"Entering Karsk environment using command: [blue]{shlex.join(args)}")
    proc = await ctx.run(*args, volumes=[(home, home, "rw")], cwd=cwd, terminal=True)
    sys.exit(await proc.wait())


@click.command("enter", help="Enter environment")
@argument_config_file
@click.argument("args", nargs=-1)
@option_prefix
@option_staging
def subcommand_enter(
    config_file: Path, prefix: Path, staging: Path, args: tuple[str, ...]
) -> None:
    if args == ():
        args = ("bash",)

    ctx = Context.from_config_file(config_file, prefix=prefix, staging=staging)
    console.log("Destination path:", ctx.prefix)
    asyncio.run(_main(ctx, *args))
