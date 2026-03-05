from __future__ import annotations
import os
from pathlib import Path
import sys
import click

from deploy.config import load_config
from deploy.package_list import PackageList


@click.command("test", help="Run tests in ./deploy_tests using pytest")
@click.argument(
    "config-file",
    type=Path,
)
@click.option(
    "--prefix",
    default="./output/prefix",
    type=Path,
)
@click.argument("args", nargs=-1)
def subcommand_test(config_file: Path, prefix: Path, args: tuple[str, ...]) -> None:
    import pytest

    config = load_config(config_file)
    plist = PackageList(config_file.parent, config, prefix=prefix)

    testpath = config_file.parent / "deploy_tests"
    if not testpath.is_dir():
        sys.exit(f"Test directory '{testpath}' doesn't exist or is not a directory")

    newpath = ":".join(str(p.out / "bin") for p in plist.packages.values())
    os.environ["PATH"] = f"{newpath}:{os.environ['PATH']}"

    for pkg in plist.packages.values():
        os.environ[f"{pkg.config.name}_version"] = pkg.config.version

    for name, dest, _ in plist.envs:
        os.environ[f"{name}_env"] = f"{prefix / dest}"

    for name, dest, _ in plist.envs:
        pkg = plist.packages[name]
        for path in (plist.prefix / dest).glob("*/manifest"):
            if path.read_text() == pkg.manifest:
                os.environ[f"{name}_env_version"] = path.parent.name
                break

    print(f"{os.environ['PATH']=}")
    sys.exit(pytest.main([str(testpath), *args]))
