from __future__ import annotations

import io
import os
import shlex
import subprocess
import sys
import asyncio
from pathlib import Path

import click

from karsk.commands._common import argument_config_file, option_staging
from karsk.config import Config, AreaConfig, load_config
from karsk.package_list import PackageList
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
        plist: PackageList,
        *,
        dry_run: bool = False,
    ) -> None:
        self._destination: Path = plist.config.destination
        self._storepath: Path = plist.config.destination / ".store"
        self._dry_run: bool = dry_run

        self._store_paths: list[Path] = [pkg.out for pkg in plist.packages.values()]

        self._env_paths: list[Path] = [
            path.parent
            for path in self._destination.glob("*/manifest")
            if not path.parent.is_symlink()
            if plist.packages[plist.config.main_package].manifest == path.read_text()
        ]

        # Create preliminary script
        self._pre_script = io.StringIO()
        self._pre_script.write("set -euxo pipefail\n")
        self._pre_script.write(f"mkdir -p {self._storepath}\n")
        self._pre_script.write(f"mkdir -p {self._destination}\n")

        # Create symlinking script
        self._post_script = io.StringIO()
        self._post_script.write("set -euxo pipefail\n")
        self._post_script.writelines(
            f"ln -sfn {os.readlink(path)} {path} \n"
            for path in self._destination.glob("*")
            if path.is_symlink()
            if (path / "manifest").is_file()
        )

    async def sync_to(self, area: AreaConfig) -> None:
        # Ensure directories are created
        await self._bash(area, self._pre_script.getvalue(), context="prescript")

        # 2. Sync .store/
        await self._rsync(area, self._store_paths, self._storepath, context=".store")

        # 3. Sync environments (eg. versions/1.0.2-2)
        await self._rsync(area, self._env_paths, self._destination)

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
    config: Config,
    staging: Path,
    no_async: bool,
    dry_run: bool,
) -> None:
    plist = PackageList(config, staging=staging)
    syncer = Sync(plist, dry_run=dry_run)

    if no_async:
        for area in config.areas:
            await syncer.sync_to(area)
        return

    results = await asyncio.gather(
        *(syncer.sync_to(area) for area in config.areas), return_exceptions=True
    )
    for index, result in enumerate(results):
        if not isinstance(result, BaseException):
            continue
        print(f"During syncing to {config.areas[index].name}:")
        raise result


@click.command("sync", help="Synchronise all locations")
@argument_config_file
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
    config_file: Path, staging: Path, no_async: bool, dry_run: bool
) -> None:
    config = load_config(config_file)
    asyncio.run(
        sync_all(
            config,
            staging=staging,
            no_async=no_async,
            dry_run=dry_run,
        )
    )
