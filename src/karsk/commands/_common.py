from __future__ import annotations
from pathlib import Path
import click


argument_config_file = click.argument("config-file", type=Path)
option_prefix = click.option("--prefix", default="./output/prefix", type=Path)
option_output = click.option("--output", default="./output", type=Path)
option_engine = click.option(
    "--engine",
    type=click.Choice(["docker", "podman", "native"]),
    default=None,
)
