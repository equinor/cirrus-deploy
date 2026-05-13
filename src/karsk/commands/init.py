from __future__ import annotations

from importlib import resources
from pathlib import Path
from karsk.console import console

import click


def _write_file(
    base: Path, name: str, format_args: dict[str, str] | None = None
) -> None:
    path = base / name
    path.parent.mkdir(parents=True, exist_ok=True)

    text = resources.files("karsk.data.templates").joinpath(f"{name}.in").read_text()

    if format_args:
        text = text.format(**format_args)

    path.write_text(text)
    console.log(f"wrote\t{path}")


@click.command("init", help="Initialize a new Karsk configuration")
@click.argument("name", type=str)
def subcommand_init(name: str) -> None:
    project_dir = Path(name)

    if project_dir.exists():
        raise click.ClickException("Project directory isn't empty")

    _write_file(project_dir, "config.yaml", {"name": name})
    _write_file(project_dir, "Containerfile")
    _write_file(
        project_dir / "karsk_tests",
        "test_version.py",
        {"name": name, "name_underscore": name.replace("-", "_")},
    )
