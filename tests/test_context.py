import os
from karsk.context import Context
import pytest


@pytest.fixture
def base_config():
    return {
        "destination": "/opt/karsk/test",
        "main-package": "",
        "entrypoint": "",
        "build-image": os.path.join(os.path.dirname(__file__), "test_build_image"),
        "packages": [],
    }


def test_minimal_config(tmp_path, base_config):
    ctx = Context.from_config(
        base_config, cwd=tmp_path, prefix=tmp_path, output=tmp_path
    )
    assert ctx.packages == {}


@pytest.mark.parametrize(
    "script_content,config_update",
    [
        pytest.param("content", {}),
        pytest.param("different content", {}),
        pytest.param(
            "content",
            {"version": "1.0"},
        ),
        pytest.param(
            "different content",
            {"version": "1.0"},
        ),
        pytest.param(
            "content",
            {"src": {"type": "git", "url": "https://example.com", "ref": "abcdefg"}},
            id="git source",
        ),
        pytest.param(
            "content",
            {"src": {"type": "file", "path": "some_file"}},
            id="file source",
        ),
    ],
)
def test_single_package(tmp_path, base_config, config_update, script_content, snapshot):
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

    ctx = Context.from_config(
        base_config, cwd=tmp_path, prefix=tmp_path, output=tmp_path
    )
    assert len(ctx.packages) == 1
    assert "A" in ctx.packages
    snapshot.assert_match(ctx.packages["A"].buildhash, "expected_hash")
