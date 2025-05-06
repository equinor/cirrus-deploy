import filecmp
import os
from subprocess import CalledProcessError
from pathlib import Path
import pytest

from deploy.build import Build
from deploy.config import Config
from deploy.links import make_links
from deploy.sync import Sync, do_sync, change_prefix

BUILD_SCRIPT = """\
#!/usr/bin/env bash

mkdir $out/bin
echo "hello world">>$out/bin/a_file
"""


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
def base_config(tmp_path):
    config = {
        "paths": {"store": Path()},
        "builds": [
            {
                "name": "A",
                "version": "0.0.0",
                "depends": [],
            },
        ],
        "envs": [{"name": "A", "dest": "location"}],
        "areas": [{"name": "destination", "host": "example.com"}],
        "links": {"location": {"latest": "^"}},
    }

    (tmp_path / "build_A.sh").write_text(BUILD_SCRIPT)
    (tmp_path / "build_A.sh").chmod(0o755)
    config = Config.model_validate(config)
    return config


def _deploy_config(config, configpath, prefix=None):
    builder = Build(
        configpath, config, extra_scripts=configpath, prefix=prefix or configpath
    )
    builder.build()
    return builder


@pytest.mark.parametrize(
    "old_prefix, new_prefix, path, expectation",
    [
        pytest.param(
            "/foo",
            "/bar",
            "/foo/file",
            "/bar/file",
            id="Simple",
        ),
        pytest.param(
            "/some/prefix",
            "/yet/another/new/prefix",
            "/some/prefix/path/in/prefix",
            "/yet/another/new/prefix/path/in/prefix",
            id="Longer path",
        ),
        pytest.param("/foo", "/bar", "/bar/file", ValueError, id="Invalid prefix"),
    ],
)
def test_change_prefix(old_prefix, new_prefix, path, expectation):
    path = Path(path)
    old_prefix = Path(old_prefix)
    new_prefix = Path(new_prefix)

    if isinstance(expectation, type) and issubclass(expectation, BaseException):
        with pytest.raises(expectation):
            change_prefix(path, old_prefix, new_prefix)
    else:
        assert change_prefix(path, old_prefix, new_prefix) == Path(expectation)


def test_successful_sync(tmp_path, base_config):
    destination = tmp_path / "destination"

    builder = _deploy_config(base_config, tmp_path)

    make_links(base_config, prefix=tmp_path)
    pkg = builder.packages["A"]
    installed_file_path = pkg.out / "bin/a_file"
    assert installed_file_path.exists()

    do_sync(
        configpath=tmp_path,
        config=base_config,
        extra_scripts=tmp_path,
        prefix=tmp_path,
        dest_prefix=destination,
    )

    synced_file_path = destination / pkg.out.name / "bin/a_file"

    assert filecmp.cmp(installed_file_path, synced_file_path, shallow=True)
    assert os.path.islink(destination / "location/latest")


def test_failing_sync(tmp_path, base_config):
    """Try to sync to non existent area"""
    _deploy_config(base_config, tmp_path)
    with pytest.raises(
        CalledProcessError,
        match=r"'example.com:/non-existent/destination'\)' returned non-zero exit status 11.",
    ):
        do_sync(
            configpath=tmp_path,
            config=base_config,
            extra_scripts=tmp_path,
            prefix=tmp_path,
            dest_prefix=Path("/non-existent/destination"),
        )
