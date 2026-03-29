from __future__ import annotations

from pathlib import Path

import click

from karsk.builder import build_all
from karsk.commands._common import argument_config_file, option_output, option_prefix
from karsk.context import Context


@click.command("build", help="Build Cirrus and dependencies")
@argument_config_file
@option_prefix
@option_output
def subcommand_build(config_file: Path, prefix: Path, output: Path) -> None:
    context = Context.from_config_file(config_file, prefix=prefix, output=output)
    build_all(context)
