from __future__ import annotations
import asyncio
from pathlib import Path
import click

from karsk.commands._common import (
    option_arch,
    option_engine,
    option_staging,
)
from karsk.engine import CpuArchNameNative, EngineName, get_engine
from karsk.paths import Paths
from karsk.wrapper import build_wrapper


@click.command("build-wrapper", help="(Re)build the wrapper program")
@option_staging
@option_engine
@option_arch
def subcommand_build_wrapper(
    staging: Path,
    engine: EngineName,
    arch: CpuArchNameNative,
) -> None:
    engine_ = get_engine(engine, arch)
    paths = Paths(staging, is_staging=True)
    _ = asyncio.run(build_wrapper(engine_, paths, rebuild=True))
