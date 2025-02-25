from deploy.build import Build
from deploy.config import Config
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
        ("content", {}, "e36260dc71ec23d2a4864cb91a6f4cf39a2382a8"),
        ("different content", {}, "417c53f6642dacd630c04b68eafbf61cd71a5808"),
        (
            "content",
            {"version": "1.0"},
            "9071d31cc26091e45c4319fbf49523da9e9076e7",
        ),
        (
            "different content",
            {"version": "1.0"},
            "7e460cb3aec91689ced8ede10f73b5572781b2c9",
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
    "script_content_A,expected_hash_A,script_content_B,expected_hash_B",
    [
        pytest.param(
            "content",
            "e36260dc71ec23d2a4864cb91a6f4cf39a2382a8",
            "content",
            "1a077b36665b28a8141efe3cae6c8a0f56a00b59",
            id="Base test",
        ),
        pytest.param(
            "changed content",
            "b1193c02fb7e0a94012f5b6887f8186069dcb50c",
            "content",
            "c4b6e82573051e913a9f3d96577c62ec8d02a287",
            id="Changes in A changes both hashes",
        ),
        pytest.param(
            "content",
            "e36260dc71ec23d2a4864cb91a6f4cf39a2382a8",
            "changed content",
            "80a25fcb95675671b025346aa92950518f461120",
            id="Changes in B only changes B's hash",
        ),
    ],
)
def test_package_dependency(
    tmp_path,
    base_config,
    script_content_A,
    expected_hash_A,
    script_content_B,
    expected_hash_B,
):
    (tmp_path / "build_A.sh").write_text(script_content_A)
    (tmp_path / "build_B.sh").write_text(script_content_B)
    base_config["builds"] = [
        {
            "name": "A",
            "version": "0.0",
            "depends": [],
        },
        {
            "name": "B",
            "version": "0.0",
            "depends": ["A"],
        },
    ]
    config = Config.model_validate(base_config)
    build = Build(Path("/dummy"), config, extra_scripts=tmp_path)
    assert len(build.packages) == 2
    assert build.packages["A"].buildhash == expected_hash_A
    assert build.packages["B"].buildhash == expected_hash_B
