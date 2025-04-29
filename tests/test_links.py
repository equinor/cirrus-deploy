from deploy.links import make_links
from deploy.config import Config

import pytest
from pathlib import Path


@pytest.fixture
def base_config():
    return {
        "paths": {"store": Path()},
        "builds": [],
        "envs": [],
        "areas": [],
        "links": {"location": {"symlink": "target"}},
    }


def _setup_env(tmp_path):
    (tmp_path / "location/target").mkdir(parents=True)


def test_make_links(tmp_path, base_config):
    _setup_env(tmp_path)
    config = Config.model_validate(base_config)
    make_links(config, prefix=tmp_path)
    assert (tmp_path / "location/symlink").exists()
