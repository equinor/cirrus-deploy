from __future__ import annotations
import os
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory
from typing import overload

from karsk.console import console
from karsk.context import Context
from karsk.engine import Engine
from karsk.paths import Paths


@overload
async def build_wrapper(engine: Context, *, rebuild: bool = False) -> Path: ...


@overload
async def build_wrapper(
    engine: Engine, paths: Paths, *, rebuild: bool = False
) -> Path: ...


async def build_wrapper(
    engine: Context | Engine,
    paths: Paths | None = None,
    *,
    rebuild: bool = False,
) -> Path:
    if isinstance(engine, Context):
        paths = engine.staging_paths
        engine = engine.engine

    assert paths is not None

    wrapper_path = paths.cache / f".wrapper.{engine.arch}"
    if wrapper_path.exists():
        if not rebuild:
            return wrapper_path
        wrapper_path.unlink()

    wrapper_src = Path(__file__).parent / "data/wrapper-rs"
    with TemporaryDirectory() as tmpdir:
        console.log(f"Building wrapper for {engine.arch}")
        proc = await engine(
            "rust:alpine",
            "cargo",
            "build",
            "--release",
            cwd="/work",
            volumes=[
                (wrapper_src, "/work", "rw"),
                (tmpdir, "/work/target", "rw"),
            ],
        )
        if await proc.wait() != os.EX_OK:
            sys.exit(proc.returncode)

        wrapper_path.parent.mkdir(parents=True, exist_ok=True)
        return shutil.copyfile(
            Path(tmpdir) / "release/wrapper",
            wrapper_path,
        )


async def install_wrapper(ctx: Context, paths: Paths) -> None:
    wrapper_path = paths.bin / ".wrapper"

    shutil.rmtree(wrapper_path.parent, ignore_errors=True)
    wrapper_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(
        await build_wrapper(ctx),
        wrapper_path,
    )
    os.chmod(wrapper_path, 0o755)

    console.log("Creating entrypoints:")
    for entry in ctx.config.entrypoints:
        console.log(f"- [blue]bin/{entry}")
        (paths.bin / entry).symlink_to(".wrapper")
