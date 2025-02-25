from src.deploy.build import Build
from src.deploy.config import Config
from pathlib import Path
import pytest


@pytest.fixture
def base_config(tmp_path):
    return {
        "paths": {"local_base": tmp_path, "system_base": "", "store": Path()},
        "builds": [],
        "envs": [],
        "areas": [],
        "links": {},
    }


def test_minimal_config(base_config):
    config = Config.model_validate(base_config)
    build = Build(Path("/dummy"), config)
    assert build.packages == {}

