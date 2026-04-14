from __future__ import annotations

from pathlib import Path

import click

from karsk.builder import install_all
from karsk.commands._common import (
    argument_config_file,
    option_engine,
    option_staging,
)
from karsk.context import Context
from karsk.engine import EngineName


@click.command("install", help="Install built packages to the destination path")
@argument_config_file
@option_staging
@option_engine
def subcommand_install(
    config_file: Path,
    staging: Path,
    engine: EngineName | None,
) -> None:
    context = Context.from_config_file(config_file, staging=staging, engine=engine)
    install_all(context)
