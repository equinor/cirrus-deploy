from __future__ import annotations

import io
import os
import shlex
import subprocess
import sys
import asyncio
from pathlib import Path

import click

from deploy.config import Config, AreaConfig, load_config
from deploy.package_list import PackageList
from deploy.utils import redirect_output


def change_prefix(path: Path, old_prefix: Path, new_prefix: Path) -> Path:
    return new_prefix / path.relative_to(old_prefix)


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
        storepath: Path,
        plist: PackageList,
        *,
        dry_run: bool = False,
        dest_prefix: Path | None = None,
    ) -> None:
        self._storepath: Path = storepath
        self._dry_run: bool = dry_run
        self._prefix = plist.prefix
        self._dest_prefix = dest_prefix or plist.prefix

        self._store_paths: list[Path] = [pkg.out for pkg in plist.packages.values()]

        self._env_paths: dict[str, list[Path]] = {
            dest: [
                path.parent
                for path in (plist.prefix / dest).glob("*/manifest")
                if not (path.parent).is_symlink()
                if plist.packages[name].manifest == path.read_text()
            ]
            for name, dest, _ in plist.envs
        }

        # Create symlinking script
        self._post_script = io.StringIO()
        self._post_script.write("set -euxo pipefail\n")
        for _, dest, _ in plist.envs:
            self._post_script.write(f"mkdir -p {self._dest_prefix / dest}\n")
            self._post_script.writelines(
                f"ln -sfn {os.readlink(path)} {change_prefix(path, plist.prefix, self._dest_prefix)} \n"
                for path in (plist.prefix / dest).glob("*")
                if path.is_symlink()
                if (path / "manifest").is_file()
            )

    async def sync_to(self, area: AreaConfig) -> None:
        # 1. Sync .store/
        await self._rsync(area, self._store_paths, self._storepath, context=".store")

        # 2. Sync environments (eg. versions/1.0.2-2)
        for dest, paths in self._env_paths.items():
            await self._rsync(area, paths, self._prefix / dest, context=dest)

        # 3. Sync all symlinks
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
            f"{area.host}:{change_prefix(parent, self._prefix, self._dest_prefix)}",
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


async def _sync(
    configpath: Path,
    config: Config,
    prefix: Path,
    dest_prefix: Path | None,
    no_async: bool,
    dry_run: bool,
) -> None:
    plist = PackageList(configpath, config, prefix=prefix)
    syncer = Sync(
        prefix / config.paths.store, plist, dry_run=dry_run, dest_prefix=dest_prefix
    )

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


def do_sync(
    configpath: Path,
    config: Config,
    *,
    prefix: Path,
    dest_prefix: Path | None = None,
    no_async: bool = False,
    dry_run: bool = False,
) -> None:
    asyncio.run(_sync(configpath, config, prefix, dest_prefix, no_async, dry_run))


@click.command("sync", help="Synchronise all locations")
@click.argument(
    "config-file",
    type=Path,
)
@click.option(
    "--prefix",
    default="./output/prefix",
    type=Path,
)
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
    config_file: Path, prefix: Path, no_async: bool, dry_run: bool
) -> None:
    config = load_config(config_file)
    do_sync(
        config_file.parent,
        config,
        prefix=prefix,
        no_async=no_async,
        dry_run=dry_run,
    )
