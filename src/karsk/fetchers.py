from __future__ import annotations
import asyncio
import os
from pathlib import Path
from aiofiles.tempfile import NamedTemporaryFile
import httpx

from karsk.config import ArchiveConfig, GitConfig
from karsk.console import console
from karsk.package import Package


async def fetch_git(config: GitConfig, path: Path) -> None:
    env = os.environ.copy()

    if config.ssh_key_path is not None:
        env["GIT_SSH_COMMAND"] = (
            f"{os.environ.get('GIT_SSH_COMMAND', 'ssh')} -i {config.ssh_key_path.absolute()}"
        )

    async def git(*args: str | Path) -> None:
        proc = await asyncio.create_subprocess_exec("git", *args, cwd=path, env=env)
        assert await proc.wait() == os.EX_OK

    try:
        path.mkdir(parents=True)
    except FileExistsError:
        await git("reset", "--hard")
        await git("clean", "-xdf")
        return

    await git("init", "-b", "main")
    await git("remote", "add", "origin", config.url)
    await git("fetch", "origin", config.ref)
    await git("checkout", "FETCH_HEAD")


async def fetch_archive(config: ArchiveConfig, path: Path) -> None:
    try:
        path.mkdir(parents=True)
    except FileExistsError:
        return

    async with NamedTemporaryFile(delete=False) as file:
        assert isinstance(file.name, (str, Path)), f"{type(file.name)=}"

        # Download
        console.log("Downloading", config.url, "to", file.name)
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "GET", config.url, follow_redirects=True
            ) as stream:
                async for chunk in stream.aiter_bytes():
                    await file.write(chunk)
        await file.close()

        # Extract using tar
        console.log("Extracting", file.name, "to", path)
        proc = await asyncio.create_subprocess_exec("tar", "xf", file.name, cwd=path)
        if await proc.wait() != 0:
            raise RuntimeError("Couldn't extract archive")

    # If the extracted archive only contains a directory at the root level, move it one up.
    files = list(path.glob("*"))
    if len(files) == 1 and files[0].is_dir():
        temp = Path.cwd() / ".src"
        files[0].rename(temp)
        path.rmdir()
        temp.rename(path)


async def fetch_single(pkg: Package) -> None:
    config = pkg.config.src
    path = pkg.src

    if isinstance(config, GitConfig):
        assert path is not None
        await fetch_git(config, path)
    elif isinstance(config, ArchiveConfig):
        assert path is not None
        await fetch_archive(config, path)
