from __future__ import annotations

import asyncio
from pathlib import Path
import sys

import click

from karsk.commands._common import argument_config_file, option_output, option_prefix
from karsk.context import Context


async def _main(ctx: Context, *args: str) -> None:
    cwd = Path.cwd()
    home = Path.home()

    # If current working directory is not inside of home, default to a safe
    # location
    if not cwd.is_relative_to(home):
        cwd = Path("/")

    proc = await ctx.run(*args, volumes=[(home, home, "rw")], cwd=cwd, terminal=True)
    sys.exit(await proc.wait())


@click.command("enter", help="Enter environment")
@argument_config_file
@click.argument("args", nargs=-1)
@option_prefix
@option_output
def subcommand_enter(
    config_file: Path, prefix: Path, output: Path, args: tuple[str, ...]
) -> None:
    if args == ():
        args = ("bash",)

    ctx = Context.from_config_file(config_file, prefix=prefix, output=output)
    asyncio.run(_main(ctx, *args))
