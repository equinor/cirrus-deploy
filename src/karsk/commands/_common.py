from __future__ import annotations
from pathlib import Path
from typing import get_args
import click

from karsk.engine import CpuArchNameNative, EngineNameNative


argument_config_file = click.argument("config-file", type=Path)
argument_areas_file = click.argument("areas-file", type=Path)
option_arch = click.option(
    "--arch",
    type=click.Choice(get_args(CpuArchNameNative)),
    default="native",
)
option_engine = click.option(
    "--engine",
    type=click.Choice(get_args(EngineNameNative)),
    default=None,
    envvar=["KARSK_ENGINE"],
)
option_staging = click.option(
    "--staging", help="Path to staging area", default="./staging", type=Path
)
