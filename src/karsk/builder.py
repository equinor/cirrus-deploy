from __future__ import annotations
import asyncio
from asyncio.subprocess import DEVNULL, PIPE
from contextlib import suppress
from datetime import datetime
import io
from itertools import chain
import os
from pathlib import Path
import shutil
import sys
from tempfile import NamedTemporaryFile, TemporaryDirectory

from karsk.console import console
from karsk.context import Context
from karsk.engine import VolumeBind
from karsk.fetchers import fetch_single
from karsk.links import make_links
from karsk.package import Package
from karsk.paths import Paths
from karsk.utils import redirect_output


SCRIPT_TEMPLATE = """#!/usr/bin/env bash
# Auto-generated wrapper script for {package_name}
# This script handles checking and forwarding arguments
# to different built versions, as well as printing available
# versions

VERSION="stable"
PRINT_VERSIONS=false
FORWARD_ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        -v)
            VERSION="${{2:?"-v requires a version argument"}}"
            shift 2
            ;;
        --print-versions)
            PRINT_VERSIONS=true
            shift
            ;;
        *)
            FORWARD_ARGS+=("$1")
            shift
            ;;
    esac
done

BASE_DIR="$(dirname "$(dirname "$(readlink -f "${{BASH_SOURCE[0]}}")")")/versions"

if [ "$PRINT_VERSIONS" = true ]; then
    NON_NUMERIC=()
    NUMERIC=()
    for entry in $(ls -1 "$BASE_DIR"); do
        [[ "$entry" == "bin" || "$entry" == .* ]] && continue
        if [ -L "$BASE_DIR/$entry" ]; then
            [[ "$entry" =~ ^[0-9]+\\.[0-9]+\\.[0-9]+ ]] && continue
            line="$entry -> $(readlink "$BASE_DIR/$entry")"
            if [[ "$entry" =~ ^[0-9] ]]; then
                NUMERIC+=("$line")
            else
                NON_NUMERIC+=("$line")
            fi
        fi
    done
    if [ ${{#NON_NUMERIC[@]}} -gt 0 ]; then
        printf '%s\\n' "${{NON_NUMERIC[@]}}" | sort -rV
    fi
    if [ ${{#NUMERIC[@]}} -gt 0 ]; then
        printf '%s\\n' "${{NUMERIC[@]}}" | awk -F' -> ' '{{
            name = $1
            n = split(name, parts, ".")
            printf "%s\\t%s\\t%s\\t%s\\n", parts[1], n, name, $0
        }}' | sort -t$'\\t' -k1,1rn -k2,2n -k3,3rV | cut -f4
    fi
    exit 0
fi

ENTRY_POINT="$BASE_DIR/$VERSION/{entrypoint}"

if [ ! -f "$ENTRY_POINT" ]; then
    echo "Error: Entry point not found: $ENTRY_POINT" >&2
    exit 1
fi

exec "$ENTRY_POINT" "${{FORWARD_ARGS[@]}}"
"""


def _create_wrapper_script(ctx: Context, bin_dir: Path) -> None:
    if not ctx.config.entrypoints:
        return

    bin_dir.mkdir(parents=True, exist_ok=True)

    for entrypoint in ctx.config.entrypoints:
        if not entrypoint.name:
            continue

        wrapper_script = bin_dir / entrypoint.name

        wrapper_script.write_text(
            SCRIPT_TEMPLATE.format(
                package_name=ctx.config.main_package,
                entrypoint=entrypoint,
            )
        )
        wrapper_script.chmod(0o755)


async def _async_build(
    ctx: Context,
    pkg: Package,
    env: dict[str, str],
    buildlog: io.TextIOWrapper,
    volumes: list[VolumeBind],
    cwd: Path,
) -> bool:
    tmpfile = NamedTemporaryFile(mode="w", prefix="karsk-builder", delete=False)
    tmpfile.writelines(
        [
            "#!/usr/bin/env bash\n",
            'echo "src: $src"\n',
            'echo "out: $out"\n',
            "set -eux -o pipefail\n",
            pkg.config.build,
        ]
    )
    os.chmod(tmpfile.name, 0o777)
    tmpfile.close()

    volumes.append((tmpfile.name, tmpfile.name, "ro"))

    proc = await ctx.engine(
        pkg.build_image,
        tmpfile.name,
        env=env,
        cwd=cwd,
        volumes=volumes,
        stdin=DEVNULL,
        stdout=PIPE,
        stderr=PIPE,
    )

    returncode, _, _ = await asyncio.gather(
        proc.wait(),
        redirect_output(pkg.config.name, proc.stdout, sys.stdout, buildlog),
        redirect_output(pkg.config.name, proc.stderr, sys.stderr, buildlog),
    )

    if returncode == 0:
        return True

    if ctx.can_debug:
        console.log(
            f"Failure during building of {pkg.fullname} (Returncode: {returncode})"
        )
        console.log("Entering interactive environment")
        console.log("$src: source for this package")
        console.log("$out: output path")
        for p in pkg.depends:
            console.log(f"${p.config.name} - output of dependency {p.fullname}")
        proc = await ctx.engine(
            pkg.build_image,
            "bash",
            env=env,
            cwd=cwd,
            volumes=volumes,
            terminal=True,
        )

        _ = await proc.wait()

    return False


async def _build(ctx: Context, pkg: Package, tmp: str) -> None:
    out = ctx.staging_paths.out(pkg)
    src = ctx.staging_paths.src(pkg)
    try:
        out.mkdir()
    except FileExistsError:
        print(
            f"Ignoring {pkg.fullname}: Already built at {out}",
            file=sys.stderr,
        )
        return

    print(f"Building {pkg.fullname}...")
    try:
        await fetch_single(ctx, pkg)
    except BaseException:
        if src is not None:
            shutil.rmtree(src)
        shutil.rmtree(out)
        raise

    env = {
        **{x.config.name: str(ctx.target_paths.out(x)) for x in pkg.depends},
        "tmp": tmp,
        "out": str(ctx.target_paths.out(pkg)),
        "CFLAGS": "-O3",
        "CXXFLAGS": "-O3",
        "FOPTFLAGS": "-O3",
        "MAKEFLAGS": "-j10",
    }

    volumes: list[VolumeBind] = [
        (ctx.staging_paths.out(x), ctx.target_paths.out(x), "ro") for x in pkg.depends
    ]
    if src is not None:
        env["src"] = (
            str(src) if ctx.engine_name == "native" else f"/tmp/pkgsrc/{src.name}"
        )

    cwd = Path("/tmp")
    if src is not None and src.is_dir():
        if ctx.engine_name == "native":
            cwd = src
        else:
            volumes.append((src, f"/tmp/pkgsrc/{src.name}", "O"))
            cwd = Path("/tmp/pkgsrc") / src.name
    elif src is not None and ctx.engine_name != "native":
        volumes.append((src, f"/tmp/pkgsrc/{src.name}", "ro"))

    volumes.append((out, ctx.target_paths.out(pkg), "rw"))

    with open(out / "build.log", "w") as buildlog:
        print("Built with https://github.com/equinor/karsk", file=buildlog)
        print(f"Build date: {datetime.now()}", file=buildlog)
        print("----- BUILD CONFIG -----", file=buildlog)
        print(pkg.config.model_dump_json(), file=buildlog)
        print("------ BUILD  LOG ------", file=buildlog)

        if not await _async_build(ctx, pkg, env, buildlog, volumes, cwd):
            for i in range(1000):
                fail_path = ctx.staging_paths.store / f"fail-{pkg.fullname}-{i}"
                if not fail_path.exists():
                    break
            else:
                sys.exit(f"Could not move failed build at {out}")

            _ = out.rename(fail_path)
            sys.exit(
                f"Building {pkg.fullname} failed. Inspect the build at: {fail_path}"
            )


async def _build_packages(ctx: Context, stop_after: Package | None = None) -> None:
    for pkg in ctx.plist.packages.values():
        with TemporaryDirectory() as tmp:
            await _build(ctx, pkg, tmp)
        if pkg is stop_after:
            console.log(f"Stopping after {pkg.config.name} as requested")
            break


def _build_envs(
    ctx: Context,
    paths: Paths,
) -> None:
    pkg = ctx.plist.packages[ctx.config.main_package]
    env_path = _get_versions_path(paths, pkg)
    if env_path is not None:
        _build_env_for_package(paths, env_path, pkg)

    default_links: dict[str, str] = {"latest": "^", "stable": "latest"}
    make_links(
        links={**default_links, **ctx.config.links},
        destination=paths.versions,
    )
    _create_wrapper_script(ctx, paths.bin)


def _build_env_for_package(paths: Paths, env_path: Path, main_package: Package) -> None:
    for pkg in chain([main_package], main_package.depends):
        out = paths.out(pkg).resolve()
        for srcdir, _, files in os.walk(out):
            dstdir = env_path / Path(srcdir).relative_to(out)
            dstdir.mkdir(parents=True, exist_ok=True)
            for f in files:
                with suppress(FileExistsError):
                    target = os.path.relpath(os.path.join(srcdir, f), dstdir.resolve())
                    os.symlink(target, os.path.join(dstdir, f))

    # Write a manifest file
    _ = (env_path / "manifest").write_text(main_package.manifest)


def _get_versions_path(paths: Paths, finalpkg: Package) -> Path | None:
    for i in range(1, 1000):
        path = paths.versions / f"{finalpkg.config.version}+{i}"
        if not path.is_dir():
            return path

        try:
            manifest = (path / "manifest").read_text()
        except FileNotFoundError:
            manifest = ""

        if finalpkg.manifest == manifest:
            print(f"Environment already exists at {path}", file=sys.stderr)
            return None

    sys.exit(
        f"Out of range while trying to find a build number for {finalpkg.config.version}"
    )


async def build_all(ctx: Context, stop_after: Package | None = None) -> None:
    await _build_packages(ctx, stop_after)
    if stop_after is not None:
        return

    _build_envs(ctx, ctx.staging_paths)


def install_all(ctx: Context) -> None:
    for pkg in ctx.plist.packages.values():
        from_path = ctx.staging_paths.out(pkg)
        to_path = ctx.target_paths.out(pkg)

        if not from_path.exists():
            sys.exit(
                f"Package {pkg.fullname} has not been built. Run 'karsk build' first."
            )
        if to_path.exists():
            print(f"Already installed: {pkg.fullname}", file=sys.stderr)
            continue
        to_path.parent.mkdir(parents=True, exist_ok=True)
        _ = shutil.copytree(from_path, to_path)
        print(f"Installed {pkg.fullname} to {to_path}")

    _build_envs(ctx, ctx.target_paths)
