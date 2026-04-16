from __future__ import annotations

import click

from karsk.commands.build import subcommand_build
from karsk.commands.build_wrapper import subcommand_build_wrapper
from karsk.commands.enter import subcommand_enter
from karsk.commands.init import subcommand_init
from karsk.commands.install import subcommand_install
from karsk.commands.schema import subcommand_schema
from karsk.commands.sync import subcommand_sync
from karsk.commands.test import subcommand_test


@click.group()
def cli() -> None:
    pass


cli.add_command(subcommand_build)
cli.add_command(subcommand_build_wrapper)
cli.add_command(subcommand_enter)
cli.add_command(subcommand_init)
cli.add_command(subcommand_install)
cli.add_command(subcommand_schema)
cli.add_command(subcommand_sync)
cli.add_command(subcommand_test)


if __name__ == "__main__":
    cli()
