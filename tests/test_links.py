import os
import pytest
from pathlib import Path

from deploy.links import make_links
from deploy.config import Config


@pytest.fixture
def base_config():
    return {
        "paths": {"store": Path()},
        "builds": [],
        "envs": [],
        "areas": [],
        "links": {"location": {"symlink": "target"}},
    }


def _setup_env(tmp_path, base_config):
    for location, symlink_config in base_config["links"].items():
        for _, target in symlink_config.items():
            (tmp_path / location / target).mkdir(parents=True)


def test_make_links(tmp_path, base_config):
    _setup_env(tmp_path, base_config)
    config = Config.model_validate(base_config)
    make_links(config, prefix=tmp_path)
    assert (tmp_path / "location/symlink").exists()


def test_make_links_fail_missing_target(tmp_path, base_config):
    # Note the lack of setting up environment, hence no target file exists
    config = Config.model_validate(base_config)
    with pytest.raises(FileNotFoundError, match="No such file or directory: 'target'"):
        make_links(config, prefix=tmp_path)


def test_make_links_on_new_package_resolves_latest(tmp_path, base_config):
    base_config["links"] = {"location": {"cool": "^"}}
    config = Config.model_validate(base_config)

    (tmp_path / "location" / "1.0.0").mkdir(parents=True)
    (tmp_path / "location" / "1.0.1").mkdir(parents=True)

    make_links(config, prefix=tmp_path)
    assert os.path.islink(tmp_path / "location/cool")
    assert os.path.realpath(tmp_path / "location/cool") == str(
        (tmp_path / "location" / "1.0.1")
    )

    # Lets create a new version
    (tmp_path / "location" / "1.0.2").mkdir(parents=True)
    make_links(config, prefix=tmp_path)
    assert os.path.realpath(tmp_path / "location/cool") == str(
        (tmp_path / "location" / "1.0.2")
    )
