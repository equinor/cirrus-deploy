from __future__ import annotations
import asyncio
from contextlib import suppress
from datetime import datetime
import io
from itertools import chain
import os
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory
from warnings import warn

from karsk.context import Context
from karsk.engine import VolumeBind
from karsk.fetchers import git_checkout
from karsk.links import make_links
from karsk.package import Package
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

BASE_DIR="$(dirname "$(dirname "$(readlink -f "${{BASH_SOURCE[0]}}")")")"

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


def _create_wrapper_script(ctx: Context) -> None:
    bin_dir = ctx.output / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)

    wrapper_script = bin_dir / "run"

    wrapper_script.write_text(
        SCRIPT_TEMPLATE.format(
            package_name=ctx.config.main_package,
            entrypoint=ctx.config.entrypoint,
        )
    )
    wrapper_script.chmod(0o755)


async def _async_build(
    ctx: Context,
    pkg: Package,
    env: dict[str, str],
    buildlog: io.TextIOWrapper,
    volumes: list[VolumeBind],
) -> None:
    cwd = Path("/tmp")

    input = "".join(
        [
            "#!/usr/bin/env bash\n",
            'echo "src: $src"\n',
            'echo "out: $out"\n',
            "set -eux -o pipefail\n",
            pkg.config.build,
        ]
    )

    proc = await ctx.engine(
        pkg.build_image,
        "bash",
        "/dev/stdin",
        env=env,
        cwd=cwd,
        volumes=volumes,
        input=input,
    )

    await asyncio.gather(
        proc.wait(),
        redirect_output(pkg.config.name, proc.stdout, sys.stdout, buildlog),
        redirect_output(pkg.config.name, proc.stderr, sys.stderr, buildlog),
    )

    assert proc.returncode == 0


def _build(ctx: Context, pkg: Package, tmp: str) -> None:
    try:
        pkg.out.mkdir()
    except FileExistsError:
        print(
            f"Ignoring {pkg.fullname}: Already built at {pkg.out}",
            file=sys.stderr,
        )
        return

    print(f"Building {pkg.fullname}...")
    try:
        git_checkout(pkg)
    except BaseException:
        if pkg.src is not None:
            shutil.rmtree(pkg.src)
        shutil.rmtree(pkg.out)
        raise

    env = {
        **{x.config.name: str(x.final_out) for x in pkg.depends},
        "tmp": tmp,
        "out": str(pkg.final_out),
    }

    volumes: list[VolumeBind] = [(x.out, x.final_out, "ro") for x in pkg.depends]
    if pkg.src is not None:
        if ctx.engine_name == "native":
            env["src"] = str(pkg.src)
        else:
            volumes.append((pkg.src, "/tmp/pkgsrc", "rw"))
            env["src"] = "/tmp/pkgsrc"
    volumes.append((pkg.out, pkg.final_out, "rw"))

    with open(pkg.out / "build.log", "w") as buildlog:
        print("Built with https://github.com/equinor/cirrus-deploy", file=buildlog)
        print(f"Build date: {datetime.now()}", file=buildlog)
        print("----- BUILD CONFIG -----", file=buildlog)
        print(pkg.config.model_dump_json(), file=buildlog)
        print("------ BUILD  LOG ------", file=buildlog)

        try:
            asyncio.run(_async_build(ctx, pkg, env, buildlog, volumes))
        except BaseException as exc:
            for i in range(1000):
                fail_path = pkg.storepath / f"fail-{pkg.fullname}-{i}"
                if not fail_path.exists():
                    break
            else:
                sys.exit(f"Could not move failed build at {pkg.out}")

            _ = pkg.out.rename(fail_path)
            sys.exit(
                f"Building {pkg.fullname} failed with exception {exc}. See failed build at: {fail_path}"
            )


def _build_packages(ctx: Context) -> None:
    for pkg in ctx.plist.packages.values():
        with TemporaryDirectory() as tmp:
            _build(ctx, pkg, tmp)


def _build_envs(ctx: Context) -> None:
    pkg = ctx.plist.packages[ctx.config.main_package]
    path = _get_build_path(ctx.output, pkg)
    assert path is not None
    _build_env_for_package(path, pkg)

    default_links: dict[str, str] = {"latest": "^", "stable": "latest"}
    make_links(
        links={**default_links, **ctx.config.links},
        prefix=ctx.output,
    )
    _create_wrapper_script(ctx)


def _build_env_for_package(base: Path, finalpkg: Package) -> None:
    for pkg in chain([finalpkg], finalpkg.depends):
        out = pkg.out.resolve()
        for srcdir, subdirs, files in os.walk(out):
            dstdir = base / srcdir[len(str(out)) + 1 :]
            dstdir.mkdir(parents=True, exist_ok=True)
            for f in files:
                with suppress(FileExistsError):
                    target = os.path.relpath(os.path.join(srcdir, f), dstdir.resolve())
                    os.symlink(target, os.path.join(dstdir, f))

    # Write a manifest file
    (base / "manifest").write_text(finalpkg.manifest)


def _get_build_path(base: Path, finalpkg: Package) -> Path | None:
    for i in range(1, 1000):
        path = base / f"{finalpkg.config.version}-{i}"
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


def build_all(ctx: Context) -> None:
    _build_packages(ctx)

    _build_envs(ctx)
