import os
from subprocess import CalledProcessError

from pathlib import Path
from karsk.builder import build_all
import pytest

from karsk.config import AreaConfig, Config
from karsk.commands.sync import Sync, sync_all
from karsk.context import Context

BUILD_SCRIPT = """\
mkdir $out/bin
echo "hello world">>$out/bin/a_file
"""


@pytest.fixture(autouse=True)
def stub_build_wrapper(mocker):
    mocker.patch("karsk.wrapper.build_wrapper", return_value=Path("/usr/bin/true"))


@pytest.fixture(autouse=True)
def fake_ssh(monkeypatch: pytest.MonkeyPatch) -> None:
    """Override Sync's SSH command so that it doesn't use SSH, and instead
    executes the command locally

    """

    # We replace RSH with an inline sh script. Both rsync and our `Sync._bash`
    # set the first argument to be the destination hostname. The remainder is
    # the command to execute on the "remote server". We simply execute it
    # locally. Then, sh sets the next argument ("fake_ssh") to be the program
    # name ($0), which is why we specify it.
    monkeypatch.setattr(Sync, "RSH", ["/bin/sh", "-c", 'shift; exec "$@"', "fake_ssh"])


@pytest.fixture
def base_config():
    config = {
        "destination": "/opt/karsk/test",
        "main-package": "A",
        "build-image": "test_build_image",
        "entrypoints": [],
        "packages": [
            {
                "name": "A",
                "version": "0.0.0",
                "depends": [],
                "build": BUILD_SCRIPT,
            },
        ],
    }

    config = Config.model_validate(config, context={"cwd": os.path.dirname(__file__)})
    return config


@pytest.fixture
def areas():
    return [AreaConfig(name="destination", host="example.com")]


async def _deploy_config(config, tmp_path):
    config.destination = tmp_path
    context = Context(config, staging=tmp_path, engine="native")
    await build_all(context)
    return context


async def test_successful_sync(tmp_path, base_config, areas):
    ctx = await _deploy_config(base_config, tmp_path)

    installed_file_path = ctx.out("A") / "bin/a_file"
    assert installed_file_path.exists()

    await sync_all(
        ctx,
        areas=areas,
        no_async=False,
        dry_run=False,
    )

    assert installed_file_path.exists()


async def test_failing_sync(tmp_path, base_config, areas, monkeypatch):
    """Try to sync with a broken RSH to simulate unreachable host"""
    ctx = await _deploy_config(base_config, tmp_path)
    monkeypatch.setattr(Sync, "RSH", ["sh", "-c", "exit 1"])
    with pytest.raises(CalledProcessError):
        await sync_all(
            ctx,
            areas=areas,
            no_async=False,
            dry_run=False,
        )


async def test_sync_with_non_local_prefix(tmp_path, base_config, areas):
    from karsk.builder import _build_envs

    base_config.destination = tmp_path

    ctx = Context(base_config, staging=tmp_path, engine="native")

    installed_file_path = ctx.out("A") / "bin/a_file"
    installed_file_path.parent.mkdir(parents=True)

    installed_file_path.write_text("test")

    await _build_envs(ctx, ctx.staging_paths)

    await sync_all(
        ctx,
        areas=areas,
        no_async=False,
        dry_run=False,
    )

    assert installed_file_path.exists()
    assert (tmp_path / "versions/latest").is_symlink()
