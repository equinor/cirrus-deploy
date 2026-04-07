import asyncio
from asyncio.subprocess import DEVNULL, PIPE, Process
from functools import partial
import hashlib
import os
from pathlib import Path
from typing import IO, Any, Literal, Protocol, TypeAlias


VolumeBind: TypeAlias = tuple[str | Path, str | Path, Literal["ro", "rw"]]
EngineName = Literal["docker", "podman", "native"]


class Engine(Protocol):
    async def __call__(
        self,
        image: Path,
        program: str | Path,
        *args: str | Path,
        volumes: list[VolumeBind] | None = None,
        env: dict[str, str],
        cwd: str | Path,
        input: str | bytes | None = None,
        stdin: int | IO[Any] | None = None,
        stdout: int | IO[Any] | None = None,
        stderr: int | IO[Any] | None = None,
        terminal: bool = False,
    ) -> Process: ...


async def _engine_has_image(
    which: Literal["docker", "podman"], image_name: str
) -> bool:
    proc = await asyncio.create_subprocess_exec(
        which, "image", "inspect", image_name, stdout=DEVNULL, stderr=DEVNULL
    )
    return await proc.wait() == os.EX_OK


async def _engine_ensure_image(which: Literal["docker", "podman"], image: Path) -> str:
    hash = hashlib.sha1(image.read_bytes()).hexdigest()[:8]
    image_name = f"karsk-env-{hash}"

    if await _engine_has_image(which, image_name):
        return image_name

    proc = await asyncio.create_subprocess_exec(
        which,
        "build",
        "--platform",
        "linux/amd64",
        "-f",
        image,
        "-t",
        image_name,
        "--label",
        "karsk",
        "/",
    )
    assert await proc.wait() == os.EX_OK
    return image_name


async def _engine(
    which: Literal["docker", "podman"],
    image: Path,
    program: str | Path,
    *args: str | Path,
    volumes: list[VolumeBind] | None = None,
    env: dict[str, str],
    cwd: str | Path,
    input: str | bytes | None = None,
    stdin: int | IO[Any] | None = None,
    stdout: int | IO[Any] | None = None,
    stderr: int | IO[Any] | None = None,
    terminal: bool = False,
) -> Process:
    assert not (stdin and input), "Arguments 'stdin' and 'input' are mutually exclusive"

    volumes = volumes or []
    image_id = await _engine_ensure_image(which, image)

    if input is not None:
        stdin = PIPE
        if isinstance(input, str):
            input = input.encode("utf-8")

    extra_args: list[str] = []
    if which == "podman":
        extra_args.extend(["--security-opt", "label=disable"])

    if terminal:
        extra_args.append("-t")

    volume_args: list[str] = []
    for src, dst, kind in volumes:
        volume_args.append(f"-v{src}:{dst}:{kind}")

    proc = await asyncio.create_subprocess_exec(
        which,
        "run",
        "--rm",
        "-i",
        *(f"-e{key}={val}" for key, val in env.items()),
        *volume_args,
        "--userns=keep-id",
        f"--workdir={cwd}",
        *extra_args,
        image_id,
        program,
        *args,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        start_new_session=True,
    )

    if input is not None:
        assert proc.stdin is not None
        proc.stdin.write(input)
        proc.stdin.close()

    return proc


async def _native(
    image: Path,
    program: str | Path,
    *args: str | Path,
    volumes: list[VolumeBind] | None = None,
    env: dict[str, str],
    cwd: str | Path,
    input: str | bytes | None = None,
    stdin: int | IO[Any] | None = None,
    stdout: int | IO[Any] | None = None,
    stderr: int | IO[Any] | None = None,
    terminal: bool = False,
) -> Process:
    _ = image, terminal

    for src, dst, _ in volumes or []:
        if src == dst:
            continue
        raise RuntimeError(
            f"When using Native engine, volume src and dst must be the same. {src=} {dst=}"
        )

    if input is not None:
        stdin = PIPE

    proc = await asyncio.create_subprocess_exec(
        program,
        *args,
        env={**os.environ, **env},
        cwd=cwd,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
    )

    if isinstance(input, str):
        input = input.encode("utf-8")
    if input is not None:
        assert proc.stdin is not None
        proc.stdin.write(input)
        proc.stdin.close()

    return proc


def get_engine(preference: EngineName | None = None) -> Engine:
    if preference is None:
        preference = "podman"

    match preference:
        case "podman":
            return partial(_engine, "podman")
        case "docker":
            return partial(_engine, "docker")
        case "native":
            return _native

    raise RuntimeError(f"Unknown OCI engine preference: {preference}")


__all__ = ["Engine", "get_engine", "VolumeBind"]
