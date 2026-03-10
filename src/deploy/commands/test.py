from __future__ import annotations
import os
from pathlib import Path
import sys
import click

from deploy.context import Context


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

    context = Context.from_config_file(
        config_file, prefix=prefix, output=Path("output")
    )

    testpath = config_file.parent / "deploy_tests"
    if not testpath.is_dir():
        sys.exit(f"Test directory '{testpath}' doesn't exist or is not a directory")

    newpath = ":".join(str(p.out / "bin") for p in context.plist.packages.values())
    os.environ["PATH"] = f"{newpath}:{os.environ['PATH']}"

    for pkg in context.plist.packages.values():
        os.environ[f"{pkg.config.name}_version"] = pkg.config.version

    print(f"{os.environ['PATH']=}")
    sys.exit(pytest.main([str(testpath), *args]))
