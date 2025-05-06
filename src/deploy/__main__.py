from __future__ import annotations

import os
import sys

import click
from pathlib import Path
from dataclasses import dataclass

from deploy.build import Build
from deploy.config import load_config
from deploy.links import make_links
from deploy.check import do_check
from deploy.package_list import PackageList
from deploy.sync import do_sync


@dataclass
class _Args:
    config_dir: Path = Path()
    prefix: Path = Path()


Args = _Args()


@click.group()
@click.option(
    "--config-dir",
    "-C",
    help="Directory of config.yaml [default=.]",
    default=".",
)
@click.option(
    "--prefix",
    "-p",
    help="Installation location",
    default="~/cirrus",
)
def cli(config_dir: str, prefix: str) -> None:
    Args.config_dir = Path(config_dir).expanduser().resolve()
    Args.prefix = Path(prefix).expanduser().resolve()


@cli.command(help="Check locations")
def check() -> None:
    config = load_config(Path(Args.config_dir))
    do_check(config, prefix=Args.prefix)


@cli.command(help="Synchronise all locations")
@click.option(
    "--no-async",
    help="Don't deploy asynchronously",
    is_flag=True,
    default=False,
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
)
@click.option(
    "--extra-scripts",
    help="Directory containing additional build scripts for the packages",
    default=None,
)
def sync(no_async: bool, dry_run: bool, extra_scripts: str) -> None:
    config = load_config(Args.config_dir)
    extra_scripts_path = (
        Path(extra_scripts).expanduser().resolve() if extra_scripts else None
    )
    do_sync(
        Args.config_dir,
        extra_scripts_path,
        config,
        prefix=Args.prefix,
        no_async=no_async,
        dry_run=dry_run,
    )


@cli.command(help="Build Cirrus and dependencies")
@click.option(
    "--force",
    "-f",
    is_flag=True,
    default=False,
    help="Force adding a new environment even if one already exists (rollback)",
)
@click.option(
    "--extra-scripts",
    help="Directory containing additional build scripts for the packages",
    default=None,
)
def build(force: bool, extra_scripts: str) -> None:
    tmp_path = Path("tmp").resolve()
    tmp_path.mkdir(parents=True, exist_ok=True)
    extra_scripts_path = (
        Path(extra_scripts).expanduser().resolve() if len(extra_scripts) > 0 else None
    )
    config = load_config(Args.config_dir)
    builder = Build(
        Args.config_dir,
        config,
        extra_scripts=extra_scripts_path,
        force=force,
        prefix=Args.prefix,
    )
    builder.build()


@cli.command(help="Generate symlinks from ./symlinks.json")
def links() -> None:
    configpath = Path.cwd()
    config = load_config(configpath)
    make_links(config, prefix=Args.prefix)


@cli.command(help="Run tests in ./deploy_tests using pytest")
@click.argument("args", nargs=-1)
def test(args: tuple[str, ...]) -> None:
    import pytest

    config = load_config(Args.config_dir)
    plist = PackageList(Args.config_dir, config, prefix=Args.prefix)

    testpath = Args.config_dir / "deploy_tests"
    if not testpath.is_dir():
        sys.exit(f"Test directory '{testpath}' doesn't exist or is not a directory")

    newpath = ":".join(str(p.out / "bin") for p in plist.packages.values())
    os.environ["PATH"] = f"{newpath}:{os.environ['PATH']}"

    for pkg in plist.packages.values():
        os.environ[f"{pkg.config.name}_version"] = pkg.config.version

    for name, dest in plist.envs:
        os.environ[f"{name}_env"] = f"{Args.prefix / dest}"

    print(f"{os.environ['PATH']=}")
    sys.exit(pytest.main([str(testpath), *args]))


if __name__ == "__main__":
    cli()
