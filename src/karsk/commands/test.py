from __future__ import annotations
from pathlib import Path
import sys
import click

from karsk.commands._common import argument_config_file, option_engine, option_staging
from karsk.context import Context
from karsk.engine import EngineName


@click.command("test", help="Run tests in ./karsk_tests using pytest")
@argument_config_file
@option_staging
@option_engine
@click.argument("args", nargs=-1)
def subcommand_test(
    config_file: Path,
    staging: Path,
    engine: EngineName | None,
    args: tuple[str, ...],
) -> None:
    import pytest
    from karsk.testing import _CONTEXT_KEY

    ctx = Context.from_config_file(config_file, staging=staging, engine=engine)
    if ctx.config.tests is None:
        raise click.ClickException(
            f"Config file '{config_file}' doesn't have 'tests' field pointing to a directory with tests"
        )

    ctx.ensure_built()

    class _KarskPlugin:
        @staticmethod
        def pytest_configure(config: pytest.Config) -> None:
            config.stash[_CONTEXT_KEY] = ctx

    sys.exit(
        pytest.main(
            [str(ctx.config.tests), *args],
            plugins=[_KarskPlugin(), "karsk.testing"],
        )
    )
