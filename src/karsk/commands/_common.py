from __future__ import annotations
from pathlib import Path
import click


argument_config_file = click.argument("config-file", type=Path)
option_staging = click.option(
    "--staging", help="Path to staging area", default="./staging", type=Path
)
option_engine = click.option(
    "--engine",
    type=click.Choice(["docker", "podman", "native"]),
    default=None,
)
