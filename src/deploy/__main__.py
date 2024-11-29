from __future__ import annotations

import os

import click
from pathlib import Path

from deploy.build import Build
from deploy.config import load_config
from deploy.links import make_links
from deploy.check import do_check
from deploy.sync import do_sync


USE_SYSTEM: bool = False


@click.group()
@click.option(
    "--system",
    "-s",
    is_flag=True,
    help="Install to /prog/pflotran instead of ~/cirrus",
    default=False,
)
def cli(system: bool) -> None:
    global USE_SYSTEM

    USE_SYSTEM = system


@cli.command(help="Check locations")
def check() -> None:
    configpath = Path.cwd()
    config = load_config(configpath)
    do_check(config)


@cli.command(help="Synchronise all locations")
def sync() -> None:
    configpath = Path.cwd()
    config = load_config(configpath)
    do_sync(config, system=USE_SYSTEM)


@cli.command(help="Build Cirrus and dependencies")
@click.option(
    "--force",
    "-f",
    is_flag=True,
    default=False,
    help="Force adding a new environment even if one already exists (rollback)",
)
def build(force: bool) -> None:
    tmp_path = Path("tmp").resolve()
    tmp_path.mkdir(parents=True, exist_ok=True)

    configpath = Path.cwd()
    config = load_config(configpath)
    builder = Build(configpath, config, force=force, system=USE_SYSTEM)
    builder.build()


@cli.command(help="Generate symlinks from ./symlinks.json")
def links() -> None:
    configpath = Path.cwd()
    config = load_config(configpath)
    make_links(config, system=USE_SYSTEM)


@cli.command(help="Run 'runcirrus' using the local installation")
@click.argument("args", nargs=-1)
def run(args: tuple[str, ...]) -> None:
    os.execlp("/prog/pflotran/bin/_runcirrus", "/prog/pflotran/bin/_runcirrus", *args)


if __name__ == "__main__":
    cli()
