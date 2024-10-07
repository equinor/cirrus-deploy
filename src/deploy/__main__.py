from __future__ import annotations

import hashlib
import os
import sys
import subprocess
from contextlib import suppress

import click
from pathlib import Path

from deploy.build import Build
from deploy.config import load_config, BuildConfig, Config

AREAS = [
    ("Bergen", "be-grid01.be.statoil.no"),
    ("Stavanger", "st-grid01.st.statoil.no"),
    ("Trondheim", "tr-grid01.tr.statoil.no"),
    ("S268 (Azure)", "s268-lckm.s268.oc.equinor.com"),  # master node of CCSDD cluster
    ("Houston, USA", "hou-grid01.hou.statoil.no"),
    ("Rio, Brazil", "rio-grid01.rio.statoil.no"),
    ("St. John, Canada", "stjohn-grid01.stjohn.statoil.no"),
]


def hash(build: BuildConfig, *other_hash: str) -> str:
    h = hashlib.sha1(usedforsecurity=False)

    h.update(build.model_dump_json().encode("utf-8"))
    with open(Path(__file__).parent / f"scripts/build_{build.name}.sh", "rb") as f:
        h.update(f.read())

    for o in other_hash:
        h.update(o.encode())

    return h.hexdigest()


@click.group()
def cli() -> None:
    pass


@cli.command(help="Check locations")
def check() -> None:
    pass


@cli.command(help="Build Cirrus and dependencies")
@click.option("--force", "-f", is_flag=True, default=False, help="Force adding a new environment even if one already exists (rollback)")
def build(force: bool) -> None:
    tmp_path = Path("tmp").resolve()
    tmp_path.mkdir(parents=True, exist_ok=True)

    config = load_config()
    builder = Build(config, force=force)
    builder.build()


@cli.command(help="Install the current version and sync to all locations")
@click.option(
    "--system",
    "-s",
    is_flag=True,
    help="Install to /prog/pflotran instead of ~/cirrus",
    default=False,
)
def install(system: bool) -> None:
    location_text = (
        click.style("/prog/pflotran", fg="red", bold=True)
        if system
        else click.style("~/cirrus", fg="green", bold=True)
    )
    click.echo(f"Installing to {location_text} in the following areas:")
    for name, host in AREAS:
        click.echo(
            f"{click.style(name, fg='green', bold=True):<35}(via: {click.style(host, bold=True)})"
        )

    if not click.confirm("Is this ok?"):
        sys.exit(1)


@cli.command(help="Generate symlinks from ./symlinks.json")
def links() -> None:
    pass


@cli.command(help="Run 'runcirrus' using the local installation")
@click.argument("args", nargs=-1)
def run(args: tuple[str, ...]) -> None:
    os.execlp("/prog/pflotran/bin/_runcirrus", "/prog/pflotran/bin/_runcirrus", *args)


if __name__ == "__main__":
    cli()
