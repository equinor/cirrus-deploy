import asyncio
from asyncio.subprocess import DEVNULL, PIPE, Process
from functools import partial
import hashlib
import os
from pathlib import Path
from platform import machine
import shlex
import shutil
import subprocess
import sys
from typing import Literal, Protocol, TypeAlias
from typing import IO, Any

from karsk.console import console


VolumeBind: TypeAlias = tuple[str | Path, str | Path, Literal["ro", "rw"]]

EngineName = Literal["docker", "podman"]
CpuArchName = Literal["arm64", "amd64"]

EngineNameNative = Literal[EngineName, "native"]
CpuArchNameNative = Literal[CpuArchName, "native", "target"]


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


async def _engine_ensure_image(
    which: EngineName,
    arch: CpuArchName,
    image: Path,
) -> str:
    hash = hashlib.sha1(image.read_bytes()).hexdigest()[:8]
    image_name = f"karsk-env-{hash}-{arch}"

    if await _engine_has_image(which, image_name):
        return image_name

    proc = await asyncio.create_subprocess_exec(
        which,
        "build",
        "--platform",
        f"linux/{arch}",
        "-f",
        image,
        "-t",
        image_name,
        "--label",
        "karsk",
        image.parent,
    )
    assert await proc.wait() == os.EX_OK
    return image_name


async def _engine(
    which: EngineName,
    arch: CpuArchName,
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
    image_id = await _engine_ensure_image(which, arch, image)

    if input is not None:
        stdin = PIPE
        if isinstance(input, str):
            input = input.encode("utf-8")

    extra_args: list[str] = []
    if which == "podman":
        extra_args.extend(["--security-opt", "label=disable"])

        # Ensure that whatever the host user's IDs are, the container user is
        # 1000:1000 (ie. the first regular user account)
        extra_args.append("--userns=keep-id:uid=1000,gid=1000")

    if terminal:
        extra_args.append("-t")

    volume_args: list[str] = []
    for src, dst, kind in volumes:
        volume_args.append(f"-v{src}:{dst}:{kind}")

    if arch != "amd64":
        console.log(
            f"[orange]Warning. Using CPU Architecture '{arch}' instead of target 'amd64'"
        )
    console.log(f"Running {str(program)} {shlex.join(map(str, args))}")
    proc = await asyncio.create_subprocess_exec(
        which,
        "run",
        "--platform",
        f"linux/{arch}",
        "--rm",
        "-i",
        *(f"-e{key}={val}" for key, val in env.items()),
        *volume_args,
        f"--workdir={cwd}",
        *extra_args,
        image_id,
        program,
        *args,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
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


def _validate_engine(which: Literal["docker", "podman"]) -> None:
    if shutil.which(which) is None:
        raise RuntimeError(
            f"'{which}' was not found in $PATH. "
            f"Please install {which} or select a different engine with --engine."
        )

    result = subprocess.run(
        [which, "version"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"'{which}' is installed but not functional:\n{result.stderr.decode().strip()}"
        )


def _normalized_cpu_arch() -> Literal["arm64", "amd64"]:
    """CPU architectures have multiple names. This returns a 'normalised'
    variant. Use the same terms as Docker.

    """
    match machine().lower():
        case "arm64" | "aarch64":
            # aarch64 is reported by Python on Linux
            return "arm64"
        case "amd64" | "x86_64":
            # x86_64 is reported by Python on Linux
            return "amd64"
        case arch:
            sys.exit(f"Unknown/unsupported CPU architecture '{arch}'")


def get_engine(
    preference: EngineNameNative | None = None, arch: CpuArchNameNative | None = None
) -> Engine:
    if preference is None:
        preference = "podman"

    arch_: CpuArchName
    if arch is None or arch == "native":
        arch_ = _normalized_cpu_arch()
    elif arch == "target":
        arch_ = "amd64"
    else:
        arch_ = arch

    match preference:
        case "podman":
            _validate_engine("podman")
            return partial(_engine, "podman", arch_)
        case "docker":
            _validate_engine("docker")
            return partial(_engine, "docker", arch_)
        case "native":
            return _native

    raise RuntimeError(f"Unknown OCI engine preference: {preference}")


__all__ = ["Engine", "get_engine", "VolumeBind"]
