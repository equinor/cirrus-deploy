from __future__ import annotations

import io
import os
import shlex
import subprocess
import sys
import asyncio
from pathlib import Path

import click

from karsk.commands._common import (
    argument_areas_file,
    argument_config_file,
    option_staging,
)
from karsk.config import AreaConfig, load_areas
from karsk.context import Context
from karsk.paths import Paths
from karsk.utils import redirect_output


class Sync:
    RSH: list[str] = [
        "ssh",
        "-q",
        "-oBatchMode=yes",
        "-oPasswordAuthentication=no",
        "-oStrictHostKeyChecking=no",
        "-oConnectTimeout=20",
    ]

    def __init__(
        self,
        ctx: Context,
        *,
        dry_run: bool = False,
        from_staging: bool = False,
    ) -> None:
        self._dry_run: bool = dry_run

        self.from_paths: Paths = ctx.staging_paths if from_staging else ctx.target_paths
        self.to_paths: Paths = ctx.target_paths

        self._store_paths: list[Path] = [
            ctx.target_paths.out(pkg) for pkg in ctx.packages.values()
        ]

        self._env_paths: list[Path] = [
            path.parent
            for path in self.from_paths.versions.glob("*/manifest")
            if not path.parent.is_symlink()
            if ctx.packages[ctx.config.main_package].manifest == path.read_text()
        ]

        # Create preliminary script
        self._pre_script: io.StringIO = io.StringIO()
        _ = self._pre_script.write("set -euxo pipefail\n")
        _ = self._pre_script.write(f"mkdir -p {self.to_paths.store}\n")
        _ = self._pre_script.write(f"mkdir -p {self.to_paths.versions}\n")

        # Create symlinking script
        self._post_script: io.StringIO = io.StringIO()
        _ = self._post_script.write("set -euxo pipefail\n")
        self._post_script.writelines(
            f"ln -sfn {os.readlink(path)} {path} \n"
            for path in self.from_paths.versions.glob("*")
            if path.is_symlink()
            if (path / "manifest").is_file()
        )

    async def sync_to(self, area: AreaConfig) -> None:
        # Ensure directories are created
        await self._bash(area, self._pre_script.getvalue(), context="prescript")

        # 2. Sync store/
        await self._rsync(
            area,
            self._store_paths,
            self.from_paths.store,
            context="store",
        )

        # 3. Sync environments (eg. versions/1.0.2+2)
        await self._rsync(
            area,
            self._env_paths,
            self.from_paths.versions,
            context="versions",
        )

        # 4. Sync all symlinks
        await self._bash(area, self._post_script.getvalue(), context="symlinks")

    async def _bash(
        self, area: AreaConfig, script: str, *, context: str | None = None
    ) -> None:
        await self._check_call(
            area,
            *self.RSH,
            area.host,
            "bash",
            input=script,
            context=context,
        )

    async def _rsync(
        self,
        area: AreaConfig,
        paths: list[Path],
        parent: Path,
        *,
        context: str | None = None,
    ) -> None:
        await self._check_call(
            area,
            "rsync",
            "-a",
            "--rsh",
            shlex.join(self.RSH),
            "--progress",
            *paths,
            f"{area.host}:{parent}",
            context=context,
        )

    async def _check_call(
        self,
        area: AreaConfig,
        program: str | Path,
        *args: str | Path,
        input: str | None = None,
        context: str | None = None,
    ) -> None:
        if self._dry_run:
            print(f"{(program, *args)}", f"{input=}")
            return

        proc = await asyncio.create_subprocess_exec(
            program,
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )

        assert proc.stdin is not None
        if input is not None:
            proc.stdin.write(input.encode())
        proc.stdin.close()

        stdout = io.StringIO()
        stderr = io.StringIO()

        await asyncio.gather(
            proc.wait(),
            redirect_output(
                f"{area.name} {repr(context)}", proc.stdout, sys.stdout, stdout
            ),
            redirect_output(
                f"{area.name} {repr(context)}", proc.stderr, sys.stderr, stderr
            ),
        )

        returncode = await proc.wait()
        if proc.returncode != 0:
            raise subprocess.CalledProcessError(
                returncode, (program, *args), stdout.getvalue(), stderr.getvalue()
            )


async def sync_all(
    ctx: Context,
    areas: list[AreaConfig],
    no_async: bool,
    dry_run: bool,
) -> None:
    syncer = Sync(ctx, dry_run=dry_run)

    if no_async:
        for area in areas:
            await syncer.sync_to(area)
        return

    results = await asyncio.gather(
        *(syncer.sync_to(area) for area in areas), return_exceptions=True
    )
    for index, result in enumerate(results):
        if not isinstance(result, BaseException):
            continue
        print(f"During syncing to {areas[index].name}:")
        raise result


@click.command("sync", help="Synchronise all locations")
@argument_config_file
@argument_areas_file
@option_staging
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
def subcommand_sync(
    config_file: Path, areas_file: Path, staging: Path, no_async: bool, dry_run: bool
) -> None:
    ctx = Context.from_config_file(config_file, staging=staging, engine="native")
    areas = load_areas(areas_file)
    asyncio.run(
        sync_all(
            ctx,
            areas=areas,
            no_async=no_async,
            dry_run=dry_run,
        )
    )
