from __future__ import annotations

import os
import sys

import click
from pathlib import Path

from deploy.build import Build
from deploy.config import load_config
from deploy.links import make_links
from deploy.check import do_check
from deploy.sync import do_sync


@click.group()
def cli() -> None:
    pass


@cli.command(help="Check locations")
def check() -> None:
    configpath = Path.cwd()
    config = load_config(configpath)
    do_check(config)


@cli.command(help="Synchronise all locations")
def sync() -> None:
    configpath = Path.cwd()
    config = load_config(configpath)
    do_sync(config)


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
    builder = Build(configpath, config, force=force)
    builder.build()


@cli.command(help="Generate symlinks from ./symlinks.json")
def links() -> None:
    configpath = Path.cwd()
    config = load_config(configpath)
    make_links(config)


@cli.command(help="Run tests in ./deploy_tests using pytest")
@click.argument("args", nargs=-1)
def test(args: tuple[str, ...]) -> None:
    import pytest

    configpath = Path.cwd()
    config = load_config(configpath)
    builder = Build(configpath, config)

    testpath = Path("./deploy_tests")
    if not testpath.is_dir():
        sys.exit(f"Test directory '{testpath}' doesn't exist or is not a directory")

    newpath = ":".join(str(p.out / "bin") for p in builder.packages.values())
    os.environ["PATH"] = f"{newpath}:{os.environ['PATH']}"

    for package in builder.packages.values():
        if not package.out.is_dir():
            sys.exit(
                f"{package.out} doesn't exist. Are you sure that '{package.fullname}' is installed?"
            )
        os.environ[f"{package.config.name}_version"] = package.config.version

    print(f"{os.environ['PATH']=}")
    sys.exit(pytest.main([str(testpath), *args]))


if __name__ == "__main__":
    cli()
