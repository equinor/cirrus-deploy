import os
from deploy.context import Context
import pytest


@pytest.fixture
def base_config():
    return {
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
    "script_content,config_update,expected_hash",
    [
        pytest.param("content", {}, "44c5769426627867bfb275daff256dd2e8fdab78"),
        pytest.param(
            "different content", {}, "a07eab34f67a22d1f6e94fb4641e53fa7af5370e"
        ),
        pytest.param(
            "content",
            {"version": "1.0"},
            "669dcf96b7f45fad31d9c873c47a3ffdafc61e44",
        ),
        pytest.param(
            "different content",
            {"version": "1.0"},
            "fd0004e7d221761def7b6da651eabd7195e4f442",
        ),
        pytest.param(
            "content",
            {"src": {"type": "git", "url": "https://example.com", "ref": "abcdefg"}},
            "8f9bce31dff425ae21a22cca7bfed1ce2f0b483a",
            id="git source",
        ),
        pytest.param(
            "content",
            {"src": {"type": "file", "path": "some_file"}},
            "44449922cc35645c8e8f1f8d782c7b97ed6daa1e",
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

    ctx = Context.from_config(
        base_config, cwd=tmp_path, prefix=tmp_path, output=tmp_path
    )
    assert len(ctx.packages) == 1
    assert "A" in ctx.packages
    assert ctx.packages["A"].buildhash == expected_hash
