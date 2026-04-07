import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from karsk.builder import build_all
from karsk.context import Context
from karsk.fetchers import git_checkout


@pytest.fixture
def base_config():
    return {
        "main-package": "",
        "entrypoint": "",
        "build-image": os.path.join(os.path.dirname(__file__), "test_build_image"),
        "packages": [],
    }


@pytest.mark.parametrize(
    "script_content,config_update",
    [
        pytest.param(
            "content",
            {"src": {"type": "git", "url": "https://example.com", "ref": "abcdefg"}},
            id="git source",
        ),
    ],
)
def test_clean_package_cache_on_rebuild(
    tmp_path, base_config, config_update, script_content
):
    with patch("karsk.fetchers.subprocess") as mocked_subprocess:
        base_config["packages"].append(
            {
                "name": "A",
                "version": "0.0",
                "depends": [],
                "build": script_content,
                **config_update,
            }
        )

        ctx = Context.from_config(
            base_config, cwd=tmp_path, prefix=tmp_path, output=tmp_path, engine="native"
        )
        pck = list(ctx.packages.values())[0]

        git_checkout(pck)

        # Checkout will use subpross run on the git command
        # We verify that it first is called with git init
        git_commands = [
            call_args[0][0][1] for call_args in mocked_subprocess.run.call_args_list
        ]
        assert "init" in git_commands

        git_checkout(pck)

        # And when we do it again, we want a git clean
        git_commands = [
            call_args[0][0][1] for call_args in mocked_subprocess.run.call_args_list
        ]
        assert "clean" in git_commands


async def test_not_overwrite_user_set_links_with_default(tmp_path, base_config):
    base_config["packages"].append(
        {"name": "test", "version": "1.0.0", "build": "mkdir -p $out/bin\n"}
    )
    base_config["main-package"] = "test"

    ctx = Context.from_config(
        base_config, cwd=tmp_path, prefix=tmp_path, output=tmp_path, engine="native"
    )
    await build_all(ctx)

    stable_link = tmp_path / "stable"
    latest_link = tmp_path / "latest"

    assert str(stable_link.readlink()) == "latest"
    assert str(latest_link.readlink()) == "1.0.0-1"
    assert stable_link.resolve() == latest_link.resolve()

    # Now we create a new build with a new version, but we set the stable link to point to the old version
    base_config["packages"] = [
        {"name": "test", "version": "1.0.1", "build": "mkdir -p $out/bin\n"}
    ]
    base_config["links"] = {"stable": "1.0.0"}

    ctx = Context.from_config(
        base_config, cwd=tmp_path, prefix=tmp_path, output=tmp_path, engine="native"
    )
    await build_all(ctx)

    assert stable_link.is_symlink()
    assert latest_link.is_symlink()
    assert str(stable_link.readlink()) == "1.0.0"
    assert str(latest_link.readlink()) == "1.0.1-1"


async def _build_wrapper(tmp_path, base_config, version="1.0.0", preamble=""):
    script = "#!/usr/bin/env bash\n"
    if preamble:
        script += f"{preamble}\n"
    script += 'echo "$@"'
    (tmp_path / "test_script.sh").write_text(script, encoding="utf-8", newline="\n")

    base_config["packages"].append(
        {
            "name": "test",
            "version": version,
            "src": {"type": "file", "path": str(tmp_path / "test_script.sh")},
            "build": """
            mkdir -p $out/bin
            cp $src $out/bin/
            chmod +x $out/bin/test_script.sh""",
        }
    )
    base_config["entrypoint"] = "bin/test_script.sh"
    base_config["main-package"] = "test"

    ctx = Context.from_config(
        base_config, cwd=tmp_path, prefix=tmp_path, output=tmp_path, engine="native"
    )
    await build_all(ctx)

    return tmp_path / "bin/run"


async def test_functional_wrapper_script(tmp_path, base_config):
    wrapper = await _build_wrapper(tmp_path, base_config)

    result = subprocess.run([wrapper], capture_output=True, text=True)
    assert result.returncode == 0
    assert result.stdout.strip() == ""

    result = subprocess.run([wrapper, "-v", "stable"], capture_output=True, text=True)
    assert result.returncode == 0
    assert result.stdout.strip() == ""

    result = subprocess.run(
        [wrapper, "-arg", "value", "-v", "stable", "pos_arg"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "-arg value pos_arg"


async def test_version_selection(tmp_path, base_config):
    await _build_wrapper(
        tmp_path, base_config, version="1.0.0", preamble='printf "v1 "'
    )

    base_config["packages"] = []
    wrapper = await _build_wrapper(
        tmp_path, base_config, version="2.0.0", preamble='printf "v2 "'
    )

    result = subprocess.run([wrapper], capture_output=True, text=True)
    assert result.returncode == 0
    assert result.stdout.strip() == "v2"

    result = subprocess.run([wrapper, "-v", "1.0.0"], capture_output=True, text=True)
    assert result.returncode == 0
    assert result.stdout.strip() == "v1"

    result = subprocess.run([wrapper, "-v", "2.0.0"], capture_output=True, text=True)
    assert result.returncode == 0
    assert result.stdout.strip() == "v2"

    result = subprocess.run(
        [wrapper, "-v", "1.0.0", "arg1", "arg2"], capture_output=True, text=True
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "v1 arg1 arg2"

    result = subprocess.run(
        [wrapper, "-v", "2.0.0", "arg1", "arg2"], capture_output=True, text=True
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "v2 arg1 arg2"


async def test_wrapper_print_versions(tmp_path, base_config):
    await _build_wrapper(tmp_path, base_config, version="1.0.0")
    await _build_wrapper(tmp_path, base_config, version="1.1.0")
    await _build_wrapper(tmp_path, base_config, version="1.1.1")

    base_config["links"] = {"something": "1.0"}
    wrapper = await _build_wrapper(tmp_path, base_config, version="2.0.0")

    result = subprocess.run(
        [wrapper, "--print-versions"], capture_output=True, text=True
    )
    assert result.returncode == 0

    lines = result.stdout.strip().splitlines()
    expected = """stable -> latest
something -> 1.0
latest -> 2.0.0-1
2 -> 2.0
2.0 -> 2.0.0
1 -> 1.1
1.1 -> 1.1.1
1.0 -> 1.0.0"""

    assert "\n".join(lines) == expected, f"Unexpected output:\n{result.stdout}"


async def test_not_overwrite_user_set_version_alias_with_default(tmp_path, base_config):
    base_config["packages"].append(
        {"name": "test", "version": "1.0.0", "build": "mkdir -p $out/bin\n"}
    )
    base_config["main-package"] = "test"

    ctx = Context.from_config(
        base_config, cwd=tmp_path, prefix=tmp_path, output=tmp_path, engine="native"
    )
    await build_all(ctx)

    assert str((tmp_path / "1.0.0").readlink()) == "1.0.0-1"
    assert str((tmp_path / "1.0").readlink()) == "1.0.0"
    assert str((tmp_path / "1").readlink()) == "1.0"

    base_config["packages"] = [
        {"name": "test", "version": "1.1.0", "build": "mkdir -p $out/bin\n"}
    ]
    base_config["links"] = {"1.1": "1.0"}

    ctx = Context.from_config(
        base_config, cwd=tmp_path, prefix=tmp_path, output=tmp_path, engine="native"
    )
    await build_all(ctx)

    assert str((tmp_path / "1.0.0").readlink()) == "1.0.0-1"
    assert str((tmp_path / "1.0").readlink()) == "1.0.0"
    assert str((tmp_path / "1.1").readlink()) == "1.0"
    assert str((tmp_path / "1").readlink()) == "1.1"


async def test_hello_world_example(tmp_path, monkeypatch):
    import shutil

    example_dir = Path(__file__).parent.parent / "examples" / "hello_world"
    work_dir = tmp_path / "hello_world"
    shutil.copytree(example_dir, work_dir, ignore=shutil.ignore_patterns("output"))

    monkeypatch.chdir(work_dir)

    ctx = Context.from_config_file(
        Path("config.yaml"), prefix=tmp_path, output=tmp_path, engine="native"
    )
    await build_all(ctx)

    wrapper = tmp_path / "bin" / "run"
    assert wrapper.exists()
    result = subprocess.run([str(wrapper)], capture_output=True, text=True)
    assert result.returncode == 0
    assert "running with args:" in result.stdout
