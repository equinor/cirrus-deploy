import os
import subprocess
from pathlib import Path
import shutil
import pytest

from karsk.config import GitConfig
from karsk.builder import build_all, _build_envs, install_all
from karsk.context import Context
from karsk.fetchers import fetch_git


@pytest.fixture
def base_config():
    return {
        "destination": "/opt/karsk/test",
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
async def test_clean_package_cache_on_rebuild(
    tmp_path, base_config, config_update, script_content, mocker
):
    process = mocker.AsyncMock("asyncio.subprocess.Process")
    process.wait = mocker.AsyncMock(
        return_value=os.EX_OK, name="asyncio.subprocess.Proccess.wait()"
    )
    create_subprocess_exec = mocker.patch(
        "asyncio.create_subprocess_exec", return_value=process
    )

    base_config["packages"].append(
        {
            "name": "foo",
            "version": "0.0",
            "depends": [],
            "build": script_content,
            **config_update,
        }
    )

    ctx = Context.from_config(
        base_config, cwd=tmp_path, staging=tmp_path, engine="native"
    )
    pkg = ctx["foo"]
    src = ctx.staging_paths.src(pkg)
    assert src is not None
    assert isinstance(pkg.config.src, GitConfig)

    await fetch_git(pkg.config.src, src)

    # Checkout will use subpross run on the git command
    # We verify that it first is called with git init
    git_commands = [
        call_args[0][1] for call_args in create_subprocess_exec.call_args_list
    ]
    assert "init" in git_commands

    await fetch_git(pkg.config.src, src)

    # And when we do it again, we want a git clean
    git_commands = [
        call_args[0][1] for call_args in create_subprocess_exec.call_args_list
    ]
    assert "clean" in git_commands


async def test_not_overwrite_user_set_links_with_default(tmp_path: Path, base_config):
    base_config["packages"].append(
        {"name": "test", "version": "1.0.0", "build": "mkdir -p $out/bin\n"}
    )
    base_config["main-package"] = "test"
    base_config["destination"] = str(tmp_path)

    ctx = Context.from_config(
        base_config, cwd=tmp_path, staging=tmp_path, engine="native"
    )
    await build_all(ctx)

    stable_link = tmp_path / "versions/stable"
    latest_link = tmp_path / "versions/latest"

    assert str(stable_link.readlink()) == "latest"
    assert str(latest_link.readlink()) == "1.0.0-1"
    assert stable_link.resolve() == latest_link.resolve()

    # Now we create a new build with a new version, but we set the stable link to point to the old version
    base_config["packages"] = [
        {"name": "test", "version": "1.0.1", "build": "mkdir -p $out/bin\n"}
    ]
    base_config["links"] = {"stable": "1.0.0"}

    ctx = Context.from_config(
        base_config, cwd=tmp_path, staging=tmp_path, engine="native"
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
    base_config["destination"] = str(tmp_path)

    ctx = Context.from_config(
        base_config, cwd=tmp_path, staging=tmp_path, engine="native"
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
    base_config["destination"] = str(tmp_path)

    ctx = Context.from_config(
        base_config, cwd=tmp_path, staging=tmp_path, engine="native"
    )
    await build_all(ctx)

    assert str((tmp_path / "versions/1.0.0").readlink()) == "1.0.0-1"
    assert str((tmp_path / "versions/1.0").readlink()) == "1.0.0"
    assert str((tmp_path / "versions/1").readlink()) == "1.0"

    base_config["packages"] = [
        {"name": "test", "version": "1.1.0", "build": "mkdir -p $out/bin\n"}
    ]
    base_config["links"] = {"1.1": "1.0"}

    ctx = Context.from_config(
        base_config, cwd=tmp_path, staging=tmp_path, engine="native"
    )
    await build_all(ctx)

    assert str((tmp_path / "versions/1.0.0").readlink()) == "1.0.0-1"
    assert str((tmp_path / "versions/1.0").readlink()) == "1.0.0"
    assert str((tmp_path / "versions/1.1").readlink()) == "1.0"
    assert str((tmp_path / "versions/1").readlink()) == "1.1"


async def test_hello_world_example(tmp_path, monkeypatch):
    import shutil
    import yaml

    example_dir = Path(__file__).parent.parent / "examples" / "hello_world"
    work_dir = tmp_path / "hello_world"
    shutil.copytree(example_dir, work_dir, ignore=shutil.ignore_patterns("output"))

    config_path = work_dir / "config.yaml"
    config_data = yaml.safe_load(config_path.read_text())
    config_data["destination"] = str(tmp_path)
    config_path.write_text(yaml.dump(config_data))

    monkeypatch.chdir(work_dir)

    ctx = Context.from_config_file(
        Path("config.yaml"), staging=tmp_path, engine="native"
    )
    await build_all(ctx)

    wrapper = tmp_path / "bin" / "run"
    assert wrapper.exists()
    result = subprocess.run([str(wrapper)], capture_output=True, text=True)
    assert result.returncode == 0
    assert "running with args:" in result.stdout


def test_build_with_non_local_prefix(tmp_path, base_config):
    from karsk.builder import _build_envs

    staging = tmp_path / "staging"

    base_config["packages"].append(
        {"name": "test", "version": "1.0.0", "build": "mkdir -p $out/bin\n"}
    )
    base_config["main-package"] = "test"

    ctx = Context.from_config(
        base_config, cwd=tmp_path, staging=staging, engine="native"
    )

    pkg = ctx.out("test")
    pkg.mkdir(parents=True)
    (pkg / "bin").mkdir()
    (pkg / "bin/hello").write_text("#!/bin/bash\necho hello\n")

    _build_envs(ctx, ctx.staging_paths)

    assert (staging / "bin/run").exists()
    assert (staging / "versions/stable").is_symlink()
    assert (staging / "versions/latest").is_symlink()


def test_install_appends_build_id_when_manifest_differs(tmp_path: Path, base_config):
    """Destination is append-only: build IDs may differ from staging.

    Scenario:
      1. Build v1.0.0 and install → both staging and destination get 1.0.0-1
      2. Clear staging, change the build script (producing a new hash)
      3. Rebuild → staging gets 1.0.0-1 again (it was cleared)
      4. Install → destination already has 1.0.0-1 with a different manifest,
         so the new build becomes 1.0.0-2

    This guarantees destination never overwrites existing builds. Build IDs
    are allowed to diverge between staging and destination, but must remain
    identical across sync locations.
    """
    staging = tmp_path / "staging"
    destination = tmp_path / "destination"

    base_config["destination"] = str(destination)
    base_config["main-package"] = "test"
    base_config["entrypoint"] = "bin/hello"
    base_config["packages"] = [
        {"name": "test", "version": "1.0.0", "build": "echo v1\n"}
    ]

    ctx1 = Context.from_config(
        base_config, cwd=tmp_path, staging=staging, engine="native"
    )
    pkg1 = ctx1.out("test")
    pkg1.mkdir(parents=True)
    (pkg1 / "bin").mkdir()
    (pkg1 / "bin/hello").write_text("v1")

    _build_envs(ctx1, ctx1.staging_paths)
    install_all(ctx1)

    assert (staging / "versions/1.0.0-1").is_dir()
    assert (destination / "versions/1.0.0-1").is_dir()

    shutil.rmtree(staging)

    base_config["packages"] = [
        {"name": "test", "version": "1.0.0", "build": "echo v2\n"}
    ]

    ctx2 = Context.from_config(
        base_config, cwd=tmp_path, staging=staging, engine="native"
    )
    pkg2 = ctx2.out("test")
    pkg2.mkdir(parents=True)
    (pkg2 / "bin").mkdir()
    (pkg2 / "bin/hello").write_text("v2")

    _build_envs(ctx2, ctx1.staging_paths)

    assert (staging / "versions/1.0.0-1").is_dir()

    install_all(ctx2)

    assert (destination / "versions/1.0.0-1").is_dir()
    assert (destination / "versions/1.0.0-2").is_dir()

    manifest1 = (destination / "versions/1.0.0-1" / "manifest").read_text()
    manifest2 = (destination / "versions/1.0.0-2" / "manifest").read_text()
    assert manifest1 != manifest2
