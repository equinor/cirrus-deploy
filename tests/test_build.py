from deploy.commands.build import Build, _checkout
from deploy.config import Config, load_config
from pathlib import Path

import subprocess
import pytest
from unittest.mock import patch


@pytest.fixture
def base_config():
    return {
        "main-package": "",
        "entrypoint": "",
        "packages": [],
    }


def test_minimal_config(tmp_path, base_config):
    config = Config.model_validate(base_config)
    build = Build(Path("/dummy"), config, prefix=tmp_path)
    assert build.packages == {}


@pytest.mark.parametrize(
    "script_content,config_update,expected_hash",
    [
        pytest.param("content", {}, "bd6cf79db824f2bd9bc774b7cb3d1fe4b00c705e"),
        pytest.param(
            "different content", {}, "1097553096e0b4aad4b08877a52cc1773c714002"
        ),
        pytest.param(
            "content",
            {"version": "1.0"},
            "0d941324747a0e908b0655622d335943c1aaacd2",
        ),
        pytest.param(
            "different content",
            {"version": "1.0"},
            "1afc69b91647e79d5cee43e8816c842789aa00c1",
        ),
        pytest.param(
            "content",
            {"src": {"type": "git", "url": "https://example.com", "ref": "abcdefg"}},
            "9c8cbbcc94f74ab126cf7a20ec4e5a016b17a46f",
            id="git source",
        ),
        pytest.param(
            "content",
            {"src": {"type": "file", "path": "some_file"}},
            "74994b22e5130b79d7eb9e3545562a718adee221",
            id="file source",
        ),
    ],
)
def test_single_package(
    tmp_path, base_config, config_update, script_content, expected_hash
):
    (tmp_path / "some_file").write_text("Some text")
    base_config["packages"].append(
        {
            "name": "A",
            "version": "0.0",
            "depends": [],
            "build": script_content,
            **config_update,
        }
    )

    config = Config.model_validate(base_config)
    build = Build(tmp_path, config, prefix=tmp_path)
    assert len(build.packages) == 1
    assert "A" in build.packages
    assert build.packages["A"].buildhash == expected_hash


@pytest.mark.parametrize(
    "script_content_A,expected_hash_A,script_content_B,expected_hash_B",
    [
        pytest.param(
            "content",
            "bd6cf79db824f2bd9bc774b7cb3d1fe4b00c705e",
            "content",
            "352cf423ae640cd95deee107c0eda948a1b6975f",
            id="Base test",
        ),
        pytest.param(
            "changed content",
            "a1c4dda62cf19d724916f4648c38ce23979dc83d",
            "content",
            "6fc357219635a6d22ddd509d90c36321ff71493f",
            id="Changes in A changes both hashes",
        ),
        pytest.param(
            "content",
            "bd6cf79db824f2bd9bc774b7cb3d1fe4b00c705e",
            "changed content",
            "c23e000403370ca163e1d5f471781aa70cc9a530",
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
    base_config["packages"] = [
        {
            "name": "A",
            "version": "0.0",
            "depends": [],
            "build": script_content_A,
        },
        {
            "name": "B",
            "version": "0.0",
            "depends": ["A"],
            "build": script_content_B,
        },
    ]
    config = Config.model_validate(base_config)
    build = Build(Path("/dummy"), config, prefix=tmp_path)
    assert len(build.packages) == 2
    assert build.packages["A"].buildhash == expected_hash_A
    assert build.packages["B"].buildhash == expected_hash_B


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
    tmp_path, base_config, config_update, script_content
):
    with patch("deploy.commands.build.subprocess") as mocked_subprocess:
        base_config["packages"].append(
            {
                "name": "A",
                "version": "0.0",
                "depends": [],
                "build": script_content,
                **config_update,
            }
        )

        config = Config.model_validate(base_config)
        build = Build(tmp_path, config, prefix=tmp_path)
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


def test_not_overwrite_user_set_links_with_default(tmp_path, base_config):
    base_config["packages"].append(
        {"name": "test", "version": "1.0.0", "build": "mkdir -p $out/bin\n"}
    )
    base_config["main-package"] = "test"

    config = Config.model_validate(base_config)
    builder = Build(tmp_path, config, extra_scripts=tmp_path, prefix=tmp_path)
    builder.build()

    stable_link = tmp_path / "stable"
    latest_link = tmp_path / "latest"

    assert str(stable_link.readlink()) == "latest"
    assert str(latest_link.readlink()) == "1.0.0-1"
    assert stable_link.resolve() == latest_link.resolve()

    # Now we create a new build with a new version, but we set the stable link to point to the old version
    base_config["packages"] = [
        {"name": "test", "version": "1.0.1", "build": "mkdir -p $out/bin\n"}
    ]
    base_config["links"] = {"stable": "1.0.0"}

    config = Config.model_validate(base_config)
    builder = Build(tmp_path, config, extra_scripts=tmp_path, prefix=tmp_path)
    builder.build()

    assert stable_link.is_symlink()
    assert latest_link.is_symlink()
    assert str(stable_link.readlink()) == "1.0.0"
    assert str(latest_link.readlink()) == "1.0.1-1"


def _build_wrapper(tmp_path, base_config, version="1.0.0", preamble=""):
    script = "#!/usr/bin/env bash\n"
    if preamble:
        script += f"{preamble}\n"
    script += 'echo "$@"'
    (tmp_path / "test_script.sh").write_text(script, encoding="utf-8", newline="\n")

    base_config["packages"].append(
        {
            "name": "test",
            "version": version,
            "src": {"type": "file", "path": str(tmp_path / "test_script.sh")},
            "build": """
            mkdir -p $out/bin
            cp $src $out/bin/
            chmod +x $out/bin/test_script.sh""",
        }
    )
    base_config["entrypoint"] = "bin/test_script.sh"
    base_config["main-package"] = "test"

    config = Config.model_validate(base_config)
    builder = Build(tmp_path, config, extra_scripts=tmp_path, prefix=tmp_path)
    builder.build()

    return tmp_path / "bin/run"


def test_functional_wrapper_script(tmp_path, base_config):
    wrapper = _build_wrapper(tmp_path, base_config)

    result = subprocess.run([wrapper], capture_output=True, text=True)
    assert result.returncode == 0
    assert result.stdout.strip() == ""

    result = subprocess.run([wrapper, "-v", "stable"], capture_output=True, text=True)
    assert result.returncode == 0
    assert result.stdout.strip() == ""

    result = subprocess.run(
        [wrapper, "-arg", "value", "-v", "stable", "pos_arg"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "-arg value pos_arg"


def test_version_selection(tmp_path, base_config):
    _build_wrapper(tmp_path, base_config, version="1.0.0", preamble='printf "v1 "')

    base_config["packages"] = []
    wrapper = _build_wrapper(
        tmp_path, base_config, version="2.0.0", preamble='printf "v2 "'
    )

    result = subprocess.run([wrapper], capture_output=True, text=True)
    assert result.returncode == 0
    assert result.stdout.strip() == "v2"

    result = subprocess.run([wrapper, "-v", "1.0.0"], capture_output=True, text=True)
    assert result.returncode == 0
    assert result.stdout.strip() == "v1"

    result = subprocess.run([wrapper, "-v", "2.0.0"], capture_output=True, text=True)
    assert result.returncode == 0
    assert result.stdout.strip() == "v2"

    result = subprocess.run(
        [wrapper, "-v", "1.0.0", "arg1", "arg2"], capture_output=True, text=True
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "v1 arg1 arg2"

    result = subprocess.run(
        [wrapper, "-v", "2.0.0", "arg1", "arg2"], capture_output=True, text=True
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "v2 arg1 arg2"


def test_wrapper_print_versions(tmp_path, base_config):
    _build_wrapper(tmp_path, base_config, version="1.0.0")
    _build_wrapper(tmp_path, base_config, version="1.1.0")
    _build_wrapper(tmp_path, base_config, version="1.1.1")

    base_config["links"] = {"something": "1.0"}
    wrapper = _build_wrapper(tmp_path, base_config, version="2.0.0")

    result = subprocess.run(
        [wrapper, "--print-versions"], capture_output=True, text=True
    )
    assert result.returncode == 0

    lines = result.stdout.strip().splitlines()
    expected = """stable -> latest
something -> 1.0
latest -> 2.0.0-1
2 -> 2.0
2.0 -> 2.0.0
1 -> 1.1
1.1 -> 1.1.1
1.0 -> 1.0.0"""

    assert "\n".join(lines) == expected, f"Unexpected output:\n{result.stdout}"


def test_not_overwrite_user_set_version_alias_with_default(tmp_path, base_config):
    base_config["packages"].append(
        {"name": "test", "version": "1.0.0", "build": "mkdir -p $out/bin\n"}
    )
    base_config["main-package"] = "test"

    config = Config.model_validate(base_config)
    builder = Build(tmp_path, config, extra_scripts=tmp_path, prefix=tmp_path)
    builder.build()

    assert str((tmp_path / "1.0.0").readlink()) == "1.0.0-1"
    assert str((tmp_path / "1.0").readlink()) == "1.0.0"
    assert str((tmp_path / "1").readlink()) == "1.0"

    base_config["packages"] = [
        {"name": "test", "version": "1.1.0", "build": "mkdir -p $out/bin\n"}
    ]
    base_config["links"] = {"1.1": "1.0"}

    config = Config.model_validate(base_config)
    builder = Build(tmp_path, config, extra_scripts=tmp_path, prefix=tmp_path)
    builder.build()

    assert str((tmp_path / "1.0.0").readlink()) == "1.0.0-1"
    assert str((tmp_path / "1.0").readlink()) == "1.0.0"
    assert str((tmp_path / "1.1").readlink()) == "1.0"
    assert str((tmp_path / "1").readlink()) == "1.1"


def test_hello_world_example(tmp_path, monkeypatch):
    import shutil

    example_dir = Path(__file__).parent.parent / "examples" / "hello_world"
    work_dir = tmp_path / "hello_world"
    shutil.copytree(example_dir, work_dir, ignore=shutil.ignore_patterns("output"))

    monkeypatch.chdir(work_dir)

    prefix = Path("output/prefix")
    config = load_config(Path("config.yaml"))
    builder = Build(Path("."), config, prefix=prefix)
    builder.build()

    wrapper = prefix / "bin" / "run"
    assert wrapper.exists()
    result = subprocess.run([str(wrapper)], capture_output=True, text=True)
    assert result.returncode == 0
    assert "running with args:" in result.stdout
