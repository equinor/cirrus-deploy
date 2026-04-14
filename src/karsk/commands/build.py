from __future__ import annotations

import asyncio
from pathlib import Path

import click

from karsk.builder import build_all
from karsk.commands._common import (
    argument_config_file,
    option_engine,
    option_staging,
)
from karsk.context import Context
from karsk.engine import EngineName
from karsk.package import Package


@click.command("build", help="Build Cirrus and dependencies")
@argument_config_file
@option_staging
@option_engine
@click.option("--package", help="Build until a given package and then stop")
def subcommand_build(
    config_file: Path,
    staging: Path,
    engine: EngineName | None,
    package: str | None,
) -> None:
    context = Context.from_config_file(config_file, staging=staging, engine=engine)

    stop_after: Package | None = None
    if package is not None:
        stop_after = context[package]

    asyncio.run(build_all(context, stop_after))
