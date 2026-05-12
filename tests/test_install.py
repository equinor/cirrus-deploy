from karsk.paths import Paths
import os
from pathlib import Path

import yaml
import pytest

from karsk.builder import build_all, install_all
from karsk.context import Context


@pytest.fixture(autouse=True)
def stub_build_wrapper(mocker):
    mocker.patch("karsk.wrapper.build_wrapper", return_value=Path("/usr/bin/true"))


@pytest.fixture
def base_config():
    return {
        "destination": "/opt/karsk/test",
        "main-package": "test",
        "entrypoints": ["test_script.sh"],
        "build-image": os.path.join(os.path.dirname(__file__), "test_build_image"),
        "packages": [],
    }


async def test_install_copies_to_destination(tmp_path, base_config):
    build_dir = tmp_path / "build"
    destination = tmp_path / "destination"
    base_config["destination"] = str(build_dir)

    (tmp_path / "script.sh").write_text(
        "#!/usr/bin/env bash\necho hello", encoding="utf-8", newline="\n"
    )
    base_config["packages"].append(
        {
            "name": "test",
            "version": "1.0.0",
            "src": {"type": "file", "path": str(tmp_path / "script.sh")},
            "build": "mkdir -p $out/bin\ncp $src $out/bin/test_script.sh\nchmod +x $out/bin/test_script.sh",
        }
    )

    ctx = Context.from_config(
        base_config, cwd=tmp_path, staging=build_dir, engine="native"
    )
    await build_all(ctx, stop_after=ctx["test"])

    assert not destination.exists()

    await install_all(ctx, target_paths=Paths(destination))

    assert destination.exists()
    assert (destination / "store").is_dir()
    assert (destination / "bin/test_script.sh").exists()
    assert (destination / "versions/latest").is_symlink()
    assert (destination / "versions/stable").is_symlink()


async def test_install_idempotent(tmp_path: Path, base_config):
    build_dir = tmp_path / "build"
    destination = tmp_path / "destination"
    base_config["destination"] = str(build_dir)

    base_config["packages"].append(
        {
            "name": "test",
            "version": "1.0.0",
            "build": "mkdir -p $out/bin\n",
        }
    )

    ctx = Context.from_config(
        base_config, cwd=tmp_path, staging=build_dir, engine="native"
    )
    await build_all(ctx, stop_after=ctx["test"])

    await install_all(ctx, target_paths=Paths(destination))
    assert (destination / "versions/1.0.0+1").is_dir()

    await install_all(ctx, target_paths=Paths(destination))
    assert (destination / "versions/1.0.0+1").is_dir()
    assert not (destination / "versions/1.0.0+2").exists()


async def test_install_hello_world_example(tmp_path, monkeypatch):
    import shutil

    example_dir = Path(__file__).parent.parent / "examples" / "hello_world"
    work_dir = tmp_path / "hello_world"
    shutil.copytree(example_dir, work_dir, ignore=shutil.ignore_patterns("output"))

    build_dir = tmp_path / "build"
    destination = tmp_path / "installed"

    config_path = work_dir / "config.yaml"
    config_data = yaml.safe_load(config_path.read_text())
    config_data["destination"] = str(build_dir)
    config_path.write_text(yaml.dump(config_data))

    monkeypatch.chdir(work_dir)

    ctx = Context.from_config_file(
        Path("config.yaml"), staging=build_dir, engine="native"
    )
    await build_all(ctx, stop_after=ctx["hello"])

    config_path.write_text(yaml.dump(config_data))

    assert not destination.exists()
    await install_all(ctx, target_paths=Paths(destination))

    assert destination.exists()
    wrapper = destination / "bin" / "binary.sh"
    assert wrapper.exists()
