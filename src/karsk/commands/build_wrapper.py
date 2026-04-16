from __future__ import annotations
import asyncio
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory
import click

from karsk.commands._common import (
    option_arch,
    option_engine,
    option_staging,
)
from karsk.context import Context
from karsk.console import console
from karsk.engine import CpuArchNameNative, EngineName, get_engine
from karsk.paths import Paths
from karsk.wrapper import build_wrapper


ENTRYPOINT_SRC = Path(__file__).parent / "../entrypoint"


async def _main(ctx: Context) -> None:
    with TemporaryDirectory() as tmpdir:
        console.log("tmpdir:", tmpdir)
        console.log("Starting")
        proc = await ctx.run(
            "cargo",
            "build",
            "--release",
            cwd="/work",
            volumes=[(tmpdir, "/work/target", "rw"), (ENTRYPOINT_SRC, "/work", "O")],
            package=[],
        )
        if await proc.wait() != 0:
            sys.exit(proc.returncode)

        ctx.staging_paths.bin.mkdir(parents=True, exist_ok=True)
        _ = shutil.copy(
            Path(tmpdir) / "release/wrapper",
            ctx.staging_paths.bin / f"wrapper.{ctx.engine.arch}",
        )


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
