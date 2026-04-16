import asyncio
from asyncio.subprocess import DEVNULL, PIPE, Process
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
from warnings import warn

from karsk.console import console


VolumeBind: TypeAlias = tuple[str | Path, str | Path, Literal["ro", "rw", "O"]]

EngineName = Literal["docker", "podman"]
CpuArchName = Literal["arm64", "amd64"]

EngineNameNative = Literal[EngineName, "native"]
CpuArchNameNative = Literal[CpuArchName, "native", "target"]


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


class Engine(Protocol):
    arch: CpuArchName
    name: EngineNameNative

    async def __call__(
        self,
        image: str | Path,
        program: str | Path,
        *args: str | Path,
        volumes: list[VolumeBind] | None = None,
        env: dict[str, str] | None = None,
        cwd: str | Path | None = None,
        input: str | bytes | None = None,
        stdin: int | IO[Any] | None = None,
        stdout: int | IO[Any] | None = None,
        stderr: int | IO[Any] | None = None,
        terminal: bool = False,
        network: bool = True,
    ) -> Process: ...


class _Engine:
    def __init__(self, engine: EngineName, arch: CpuArchName) -> None:
        self.arch: CpuArchName = arch
        self.name: EngineNameNative = engine

        if shutil.which(engine) is None:
            raise RuntimeError(
                f"'{engine}' was not found in $PATH. "
                f"Please install {engine} or select a different engine with --engine."
            )

        result = subprocess.run(
            [engine, "version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"'{engine}' is installed but not functional:\n{result.stderr.decode().strip()}"
            )

    async def _has_image(self, image_name: str) -> bool:
        proc = await asyncio.create_subprocess_exec(
            self.name, "image", "inspect", image_name, stdout=DEVNULL, stderr=DEVNULL
        )
        return await proc.wait() == os.EX_OK

    async def _ensure_image(self, image: Path) -> str:
        hash = hashlib.sha1(image.read_bytes()).hexdigest()[:8]
        image_name = f"karsk-env-{hash}-{self.arch}"

        if await self._has_image(image_name):
            return image_name

        proc = await asyncio.create_subprocess_exec(
            self.name,
            "build",
            "--platform",
            f"linux/{self.arch}",
            "-f",
            image,
            "-t",
            image_name,
            "--label",
            "karsk",
            image.parent,
        )
        if await proc.wait() != os.EX_OK:
            sys.exit(proc.returncode)
        return image_name

    async def __call__(
        self,
        image: str | Path,
        program: str | Path,
        *args: str | Path,
        volumes: list[VolumeBind] | None = None,
        env: dict[str, str] | None = None,
        cwd: str | Path | None = None,
        input: str | bytes | None = None,
        stdin: int | IO[Any] | None = None,
        stdout: int | IO[Any] | None = None,
        stderr: int | IO[Any] | None = None,
        terminal: bool = False,
        network: bool = True,
    ) -> Process:
        assert not (stdin and input), (
            "Arguments 'stdin' and 'input' are mutually exclusive"
        )

        volumes = volumes or []
        if isinstance(image, str):
            image_id = image
        else:
            image_id = await self._ensure_image(image)

        if input is not None:
            stdin = PIPE
            if isinstance(input, str):
                input = input.encode("utf-8")

        extra_args: list[str] = []
        if self.name == "podman":
            extra_args.extend(["--security-opt", "label=disable"])

            # Ensure that whatever the host user's IDs are, the container user is
            # 1000:1000 (ie. the first regular user account)
            extra_args.append("--userns=keep-id:uid=1000,gid=1000")

        if terminal:
            extra_args.append("-t")

        if not network:
            extra_args.append("--network=none")

        volume_args: list[str] = []
        for src, dst, kind in volumes:
            volume_args.append(f"-v{src}:{dst}:{kind}")

        if self.arch != "amd64":
            console.log(
                f"[orange]Warning. Using CPU Architecture '{self.arch}' instead of target 'amd64'"
            )
        console.log(f"Running {str(program)} {shlex.join(map(str, args))}")
        proc = await asyncio.create_subprocess_exec(
            self.name,
            "run",
            "--platform",
            f"linux/{self.arch}",
            "--rm",
            "-i",
            *(f"-e{key}={val}" for key, val in (env or {}).items()),
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


class _Native:
    arch: CpuArchName = _normalized_cpu_arch()
    name: EngineNameNative = "native"

    async def __call__(
        self,
        image: str | Path,
        program: str | Path,
        *args: str | Path,
        volumes: list[VolumeBind] | None = None,
        env: dict[str, str] | None = None,
        cwd: str | Path | None = None,
        input: str | bytes | None = None,
        stdin: int | IO[Any] | None = None,
        stdout: int | IO[Any] | None = None,
        stderr: int | IO[Any] | None = None,
        terminal: bool = False,
        network: bool = True,
    ) -> Process:
        _ = image, terminal

        if not network:
            warn("Native OCI engine doesn't support running without network")

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
            env={**os.environ, **(env or {})},
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
            return _Engine("podman", arch_)
        case "docker":
            return _Engine("docker", arch_)
        case "native":
            return _Native()

    raise RuntimeError(f"Unknown OCI engine preference: {preference}")


__all__ = ["Engine", "get_engine", "VolumeBind"]
