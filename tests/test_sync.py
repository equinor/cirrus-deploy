import filecmp
from subprocess import CalledProcessError

from deploy.build import Build
from deploy.config import Config
from pathlib import Path
import pytest

from deploy.sync import do_sync

BUILD_SCRIPT = """\
#!/usr/bin/env bash

mkdir $out/bin
echo "hello world">>$out/bin/a_file
"""


async def async_no_op(*_args):
    pass


def mocked_format_dest_path(area, path, dest):
    # Original function defines this as area.host:path, where area will be
    # the same in both source and destination. We mock this setup and
    # disregard the host (i.e. no ssh) and allow a different destination
    # instead of source
    # We wrap this function in a lambda that passes on dest (as that is
    # not included in the original one. Similar behavoir as partial,
    # without including functools
    return dest


def setup_fake_sync(monkeypatch: pytest.MonkeyPatch, destination: str) -> None:
    import deploy.sync

    async def no_op(*args, **kwargs) -> None:
        pass

    def format_dest_path(*_) -> str:
        return destination

    monkeypatch.setattr(deploy.sync.Sync, "_format_dest_path", format_dest_path)
    monkeypatch.setattr(deploy.sync.Sync, "_bash", no_op)


@pytest.fixture
def base_config(tmp_path):
    config = {
        "paths": {"store": Path()},
        "builds": [
            {
                "name": "A",
                "version": "0.0",
                "depends": [],
            },
        ],
        "envs": [],
        "areas": [{"name": "test-destination", "host": "localhost"}],
        "links": {},
    }

    (tmp_path / "build_A.sh").write_text(BUILD_SCRIPT)
    (tmp_path / "build_A.sh").chmod(0o755)
    config = Config.model_validate(config)
    return config


def _deploy_config(config, configpath):
    builder = Build(configpath, config, extra_scripts=configpath, prefix=configpath)
    builder.build()
    return builder


def test_successful_sync(tmp_path, monkeypatch, base_config):
    destination = tmp_path / "destination"
    setup_fake_sync(monkeypatch, str(destination))

    builder = _deploy_config(base_config, tmp_path)
    pkg = builder.packages["A"]
    installed_file_path = pkg.out / "bin/a_file"
    assert installed_file_path.exists()

    do_sync(
        configpath=tmp_path,
        config=base_config,
        extra_scripts=tmp_path,
        prefix=tmp_path,
    )

    synced_file_path = destination / pkg.out.name / "bin/a_file"

    assert filecmp.cmp(installed_file_path, synced_file_path, shallow=True)


def test_failing_sync(tmp_path, monkeypatch, base_config):
    """Try to sync to non existent area"""
    setup_fake_sync(monkeypatch, "/non-existent/destination")

    _deploy_config(base_config, tmp_path)
    with pytest.raises(
        CalledProcessError,
        match="'/non-existent/destination'\\)' returned non-zero exit status 11.",
    ):
        do_sync(
            configpath=tmp_path,
            config=base_config,
            extra_scripts=tmp_path,
            prefix=tmp_path,
        )
