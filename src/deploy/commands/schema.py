from __future__ import annotations
from pathlib import Path

import click
import json
from deploy.config import Config


@click.command("schema", help="Generate JSON Schema")
@click.option("-o", "--output", default="/dev/stdout", type=Path, help="Output file")
def subcommand_schema(output: Path) -> None:
    with open(output, "w") as f:
        json.dump(Config.model_json_schema(), f)
        f.write("\n")
