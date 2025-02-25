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


@pytest.mark.parametrize(
    "script_content,config_update,expected_hash",
    [
        ("content", {}, "4810d7a46d77ed66ab7742ec30f3dbaf39465fed"),
        ("different content", {}, "6e1442405bac72ea3360c8c05222a7b2ce89d2ab"),
        (
            "content",
            {"version": "1.0"},
            "b5808cd0ac9adcc5543ccbb49f77249bfadd957d",
        ),
        (
            "different content",
            {"version": "1.0"},
            "0808eb99124bf80a3292f14ca7de219384a7464b",
        ),
    ],
)
def test_single_package(
    tmp_path, base_config, config_update, script_content, expected_hash
):
    (tmp_path / "build_A.sh").write_text(script_content)
    base_config["builds"].append(
        {
            "name": "A",
            "version": "0.0",
            "src": {"type": "file", "path": "some"},
            "depends": [],
            **config_update,
        }
    )

    config = Config.model_validate(base_config)
    build = Build(Path("/dummy"), config, extra_scripts=tmp_path)
    assert len(build.packages) == 1
    assert "A" in build.packages
    assert build.packages["A"].buildhash == expected_hash


@pytest.mark.parametrize(
    "script_content_A,config_update_A,expected_hash_A,script_content_B,config_update_B,expected_hash_B",
    [
        (
            "content",
            {},
            "4810d7a46d77ed66ab7742ec30f3dbaf39465fed",
            "content",
            {},
            "f5d262be810ba18a81c63f416ab19cef1a6a6dd9",
        ),
    ],
)
def test_package_dependency(
    tmp_path,
    base_config,
    script_content_A,
    config_update_A,
    expected_hash_A,
    script_content_B,
    config_update_B,
    expected_hash_B,
):
    (tmp_path / "build_A.sh").write_text(script_content_A)
    (tmp_path / "build_B.sh").write_text(script_content_B)
    base_config["builds"] = [
        {
            "name": "A",
            "version": "0.0",
            "src": {"type": "file", "path": "some"},
            "depends": [],
            **config_update_A,
        },
        {
            "name": "B",
            "version": "0.0",
            "src": {"type": "file", "path": "some"},
            "depends": ["A"],
            **config_update_B,
        },
    ]
    config = Config.model_validate(base_config)
    build = Build(Path("/dummy"), config, extra_scripts=tmp_path)
    assert len(build.packages) == 2
    assert build.packages["A"].buildhash == expected_hash_A
    assert build.packages["B"].buildhash == expected_hash_B
