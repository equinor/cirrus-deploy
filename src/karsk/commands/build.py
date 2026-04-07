from __future__ import annotations

import asyncio
from pathlib import Path

import click

from karsk.builder import build_all
from karsk.commands._common import (
    argument_config_file,
    option_engine,
    option_output,
    option_prefix,
)
from karsk.context import Context
from karsk.engine import EngineName


@click.command("build", help="Build Cirrus and dependencies")
@argument_config_file
@option_prefix
@option_output
@option_engine
def subcommand_build(
    config_file: Path, prefix: Path, output: Path, engine: EngineName | None
) -> None:
    context = Context.from_config_file(
        config_file, prefix=prefix, output=output, engine=engine
    )
    asyncio.run(build_all(context))
