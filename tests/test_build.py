import re
from deploy.build import Build
from deploy.config import Config
from pathlib import Path
import pytest
from unittest.mock import patch
from deploy.build import _checkout


@pytest.fixture
def base_config(tmp_path):
    return {
        "paths": {"store": Path()},
        "builds": [],
        "envs": [],
        "areas": [],
        "links": {},
    }


def test_minimal_config(tmp_path, base_config):
    config = Config.model_validate(base_config)
    build = Build(Path("/dummy"), config, prefix=tmp_path)
    assert build.packages == {}


@pytest.mark.parametrize(
    "script_content,config_update,expected_hash",
    [
        pytest.param("content", {}, "e36260dc71ec23d2a4864cb91a6f4cf39a2382a8"),
        pytest.param(
            "different content", {}, "417c53f6642dacd630c04b68eafbf61cd71a5808"
        ),
        pytest.param(
            "content",
            {"version": "1.0"},
            "9071d31cc26091e45c4319fbf49523da9e9076e7",
        ),
        pytest.param(
            "different content",
            {"version": "1.0"},
            "7e460cb3aec91689ced8ede10f73b5572781b2c9",
        ),
        pytest.param(
            "content",
            {"src": {"type": "git", "url": "https://example.com", "ref": "abcdefg"}},
            "29babb628169cbc393ded61e18ee8d4e906a3a34",
            id="git source",
        ),
        pytest.param(
            "content",
            {"src": {"type": "file", "path": "build_A.sh"}},
            "4881eaad3331c6285babfa160920db1d9cd19e35",
            id="file source",
        ),
    ],
)
def test_single_package(
    tmp_path, base_config, config_update, script_content, expected_hash
):
    (tmp_path / "build_A.sh").write_text(script_content)
    (tmp_path / "build_A.sh").chmod(0o755)
    base_config["builds"].append(
        {
            "name": "A",
            "version": "0.0",
            "depends": [],
            **config_update,
        }
    )

    config = Config.model_validate(base_config)
    build = Build(tmp_path, config, extra_scripts=tmp_path, prefix=tmp_path)
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
    (tmp_path / "build_A.sh").chmod(0o755)
    (tmp_path / "build_B.sh").write_text(script_content_B)
    (tmp_path / "build_B.sh").chmod(0o755)
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
    build = Build(Path("/dummy"), config, extra_scripts=tmp_path, prefix=tmp_path)
    assert len(build.packages) == 2
    assert build.packages["A"].buildhash == expected_hash_A
    assert build.packages["B"].buildhash == expected_hash_B


def test_build_script_validity(
    tmp_path,
    base_config,
):
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

    # Test that if no files are present, the first package will error
    with pytest.raises(
        SystemExit,
        match=re.escape(
            "Build script for package A (build_A.sh) wasn't found or it isn't executable"
        ),
    ):
        _ = Build(Path("/dummy"), config, extra_scripts=tmp_path, prefix=tmp_path)

    # Test that if both files exist, but only the first one is executable, we'll
    # error on the second
    (tmp_path / "build_A.sh").write_text("")
    (tmp_path / "build_A.sh").chmod(0o755)
    (tmp_path / "build_B.sh").write_text("")
    with pytest.raises(
        SystemExit,
        match=re.escape(
            "Build script for package B (build_B.sh) wasn't found or it isn't executable"
        ),
    ):
        _ = Build(Path("/dummy"), config, extra_scripts=tmp_path, prefix=tmp_path)

    # Check that the correct configuration is correct
    (tmp_path / "build_B.sh").chmod(0o755)
    Build(Path("/dummy"), config, extra_scripts=tmp_path, prefix=tmp_path)


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
def test_clean_package_cache_on_rebuild(
    tmp_path, base_config, monkeypatch, config_update, script_content
):
    with patch("deploy.build.subprocess") as mocked_subprocess:
        monkeypatch.setenv("XDG_CACHE_HOME", tmp_path)
        (tmp_path / "build_A.sh").write_text(script_content)
        (tmp_path / "build_A.sh").chmod(0o755)
        base_config["builds"].append(
            {
                "name": "A",
                "version": "0.0",
                "depends": [],
                **config_update,
            }
        )

        config = Config.model_validate(base_config)
        build = Build(tmp_path, config, extra_scripts=tmp_path, prefix=tmp_path)
        pck = list(build.packages.values())[0]

        _checkout(pck)

        # Checkout will use subpross run on the git command
        # We verify that it first is called with git init
        git_commands = [
            call_args[0][0][1] for call_args in mocked_subprocess.run.call_args_list
        ]
        assert "init" in git_commands

        _checkout(pck)

        # And when we do it again, we want a git clean
        git_commands = [
            call_args[0][0][1] for call_args in mocked_subprocess.run.call_args_list
        ]
        assert "clean" in git_commands
