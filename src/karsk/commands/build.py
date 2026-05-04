from __future__ import annotations

import asyncio
from pathlib import Path

import click

from karsk.builder import build_all
from karsk.commands._common import (
    argument_config_file,
    option_arch,
    option_engine,
    option_staging,
)
from karsk.context import Context
from karsk.engine import CpuArchNameNative, EngineNameNative
from karsk.package import Package


@click.command("build", help="Build selected package and dependencies")
@argument_config_file
@option_staging
@option_arch
@option_engine
@click.option("--package", help="Build until a given package and then stop")
def subcommand_build(
    config_file: Path,
    staging: Path,
    engine: EngineNameNative | None,
    package: str | None,
    arch: CpuArchNameNative,
) -> None:
    context = Context.from_config_file(
        config_file, staging=staging, engine=engine, arch=arch
    )

    stop_after: Package | None = None
    if package is not None:
        stop_after = context[package]

    asyncio.run(build_all(context, stop_after))
