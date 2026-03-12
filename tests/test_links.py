import os
import pytest
from pathlib import Path

from deploy.links import make_links


@pytest.fixture
def base_config():
    return {
        "paths": {"store": Path()},
        "builds": [],
        "areas": [],
        "links": {"location": {"symlink": "target"}},
    }


def _setup_env(tmp_path, base_config):
    for location, symlink_config in base_config["links"].items():
        for _, target in symlink_config.items():
            (tmp_path / location / target).mkdir(parents=True)


def test_make_links(tmp_path, base_config):
    _setup_env(tmp_path, base_config)
    make_links(base_config["links"]["location"], prefix=tmp_path / "location")
    assert (tmp_path / "location/symlink").exists()


def test_make_links_fail_missing_target(tmp_path, base_config):
    with pytest.raises(FileNotFoundError, match="No such file or directory: 'target'"):
        make_links(base_config["links"]["location"], prefix=tmp_path / "location")


def test_make_links_on_new_package_resolves_latest(tmp_path, base_config):
    base_config["links"] = {"location": {"cool": "^"}}

    (tmp_path / "location" / "1.0.0-1").mkdir(parents=True)
    (tmp_path / "location" / "1.0.1-1").mkdir(parents=True)

    make_links(base_config["links"]["location"], prefix=tmp_path / "location")
    assert os.path.islink(tmp_path / "location/cool")
    assert os.path.realpath(tmp_path / "location/cool") == str(
        (tmp_path / "location" / "1.0.1-1")
    )

    (tmp_path / "location" / "1.0.2-1").mkdir(parents=True)
    make_links(base_config["links"]["location"], prefix=tmp_path / "location")
    assert os.path.realpath(tmp_path / "location/cool") == str(
        (tmp_path / "location" / "1.0.2-1")
    )


def test_auto_version_aliases_created(tmp_path):
    prefix = tmp_path / "location"
    (prefix / "1.0.0-1").mkdir(parents=True)
    (prefix / "1.1.0-1").mkdir(parents=True)
    (prefix / "1.1.1-1").mkdir(parents=True)

    make_links({}, prefix=prefix)

    assert os.readlink(prefix / "1.0.0") == "1.0.0-1"
    assert os.readlink(prefix / "1.1.0") == "1.1.0-1"
    assert os.readlink(prefix / "1.1.1") == "1.1.1-1"
    assert os.readlink(prefix / "1.0") == "1.0.0"
    assert os.readlink(prefix / "1.1") == "1.1.1"
    assert os.readlink(prefix / "1") == "1.1"


def test_auto_version_aliases_reflects_latest_build(tmp_path):
    prefix = tmp_path / "location"
    (prefix / "1.0.0-1").mkdir(parents=True)
    (prefix / "1.0.0-2").mkdir(parents=True)
    (prefix / "1.0.1-1").mkdir(parents=True)
    (prefix / "1.0.1-2").mkdir(parents=True)

    make_links({}, prefix=prefix)

    assert os.readlink(prefix / "1.0.0") == "1.0.0-2"
    assert os.readlink(prefix / "1.0.1") == "1.0.1-2"
    assert os.readlink(prefix / "1.0") == "1.0.1"
    assert os.readlink(prefix / "1") == "1.0"


def test_auto_version_aliases_user_override(tmp_path):
    prefix = tmp_path / "location"
    (prefix / "1.0.0-1").mkdir(parents=True)
    (prefix / "1.1.0-1").mkdir(parents=True)
    (prefix / "1.1.1-1").mkdir(parents=True)

    make_links({"1.1": "1.1.0"}, prefix=prefix)

    assert os.readlink(prefix / "1.1") == "1.1.0"
    assert os.readlink(prefix / "1") == "1.1"


def test_auto_version_aliases_multiple_majors(tmp_path):
    prefix = tmp_path / "location"
    (prefix / "1.0.0-1").mkdir(parents=True)
    (prefix / "2.0.0-1").mkdir(parents=True)
    (prefix / "2.1.0-1").mkdir(parents=True)

    make_links({}, prefix=prefix)

    assert os.readlink(prefix / "1.0") == "1.0.0"
    assert os.readlink(prefix / "1") == "1.0"
    assert os.readlink(prefix / "2.0") == "2.0.0"
    assert os.readlink(prefix / "2.1") == "2.1.0"
    assert os.readlink(prefix / "2") == "2.1"
