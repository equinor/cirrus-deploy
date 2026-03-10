from __future__ import annotations
import asyncio
import hashlib
import os
from abc import ABC, abstractmethod
from pathlib import Path
import sys
from typing import Literal
from subprocess import check_output, run


type VolumeBind = tuple[str | Path, str | Path, Literal["ro", "rw"]]


class Engine(ABC):
    @abstractmethod
    async def exec(
        self,
        image: str | Path,
        program: str | Path,
        *args: str | Path,
        volumes: list[VolumeBind] | None = None,
        allow_network: bool = False,
        cwd: str,
    ) -> asyncio.subprocess.Process: ...


class Podman(Engine):
    def __init__(self):
        version = check_output(["podman", "version"], text=True)
        if "Podman Engine" not in version:
            raise RuntimeError("podman not available")

    def has_image(self, image_name: str) -> bool:
        status = run(["podman", "image", "exists", image_name])
        return status.returncode == os.EX_OK

    def ensure_image(self, image: str | Path) -> str:
        image = Path(image)
        hash = hashlib.sha1(image.read_bytes()).hexdigest()[:8]

        image_name = f"karsk-env-{hash}"

        if not self.has_image(image_name):
            print(f"> Building container image {image_name} <")
            run(
                [
                    "podman",
                    "build",
                    "--platform",
                    "amd64",
                    "-f",
                    image,
                    "-t",
                    image_name,
                    "--label",
                    "karsk-env",
                ],
                check=True,
            )
        return image_name

    async def exec(
        self,
        image: str | Path,
        program: str | Path,
        *args: str | Path,
        volumes: list[VolumeBind] | None = None,
        allow_network: bool = False,
        env: dict[str, str],
        cwd: str,
    ) -> asyncio.subprocess.Process:
        if volumes is None:
            volumes = []

        image_id = self.ensure_image(image)

        print("> Running container <")
        return await asyncio.create_subprocess_exec(
            "podman",
            "run",
            "--security-opt",
            "label=disable",
            "--rm",
            "-it",
            *(f"-e{key}={val}" for key, val in env.items()),
            "-v/tmp:/tmp:rw",
            *(
                f"-v{Path(vol_src).absolute()}:{Path(vol_dst).absolute()}:{mount_type}"
                for vol_src, vol_dst, mount_type in volumes
            ),
            "--userns=keep-id",
            "--workdir=/tmp/pkgsrc",
            # *(() if allow_network else ("--network=none",)),
            image_id,
            program,
            *args,
        )


def get_oci_engine() -> Engine:
    preferences: list[str] = ["podman", "docker"]
    if sys.platform == "darwin":
        preferences = ["docker", "podman"]

    for preference in preferences:
        try:
            match preference:
                case "podman":
                    return Podman()
                case "docker":
                    raise NotImplementedError("No docker support")
                case _:
                    raise NotImplementedError(f"Unknown OCI engine '{preference}'")

        except RuntimeError:
            continue

    raise RuntimeError("Exit!")


if __name__ == "__main__":
    engine = get_oci_engine()

    engine.exec("Dockerfile", "/bin/bash", "-c", "echo Hello!")
