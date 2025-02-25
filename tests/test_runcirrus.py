import os
import sys
import importlib.util
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def runcirrus():
    """Python doesn't know where to look for runcirrus.py, so we can't simply
    import it. Instead, and to avoid explicitly modifying `sys.path`, we
    dynamically import the file under the `runcirrus` module name.

    This seems less hacky.

    """

    file_location = (
        Path(os.path.dirname(__file__)).parent / "src/deploy/scripts/runcirrus.py"
    ).resolve()

    spec = importlib.util.spec_from_file_location("runcirrus", file_location)
    assert spec is not None
    assert spec.loader is not None

    runcirrus = importlib.util.module_from_spec(spec)

    sys.modules["runcirrus"] = runcirrus
    spec.loader.exec_module(runcirrus)
    return runcirrus


def test_printversions_empty_folder(capsys, tmp_path, monkeypatch, runcirrus):
    monkeypatch.setenv("CIRRUS_VERSIONS_PATH", str(tmp_path))
    with pytest.raises(SystemExit):
        runcirrus.parse_args(["0", "--print-versions"])

    assert capsys.readouterr().out == f"No installed versions found at {tmp_path}\n"


@pytest.mark.parametrize(
    "dirs,expected_out", [(["1.10"], "1.10\n"), (["1.10", ".store"], "1.10\n")]
)
def test_printversions_ignore_hidden(
    dirs, expected_out, capsys, tmp_path, monkeypatch, runcirrus
):
    for name in dirs:
        (tmp_path / name).mkdir()
    monkeypatch.setenv("CIRRUS_VERSIONS_PATH", str(tmp_path))

    with pytest.raises(SystemExit):
        runcirrus.parse_args(["0", "--print-versions"])

    assert capsys.readouterr().out == expected_out


@pytest.mark.parametrize(
    "script_name,expect",
    [
        ("runcirrus", "stable"),
        ("runpflotran", "1.8"),
        ("runpflotran1.8.12", "1.8.12"),
        ("runpflotran1.8-openpbs-rh8", "1.8"),
    ],
)
def test_default_version(script_name, expect, runcirrus):
    assert runcirrus.default_version(script_name) == expect, f"{script_name=}"


@pytest.mark.parametrize(
    "dir,expected_out",
    [
        (
            "cirrus/versions/.store/d312321-runcirrus-1.0.0/bin/runcirrus",
            "cirrus/versions",
        ),
        ("cirrus/versions/.store/further_up", "cirrus/versions"),
    ],
)
def test_get_versions_path_correctly_identifies_location(
    dir, expected_out, tmp_path, monkeypatch, runcirrus
):
    def mockreturn(_):
        return dir

    monkeypatch.setattr(os.path, "dirname", mockreturn)

    assert str(runcirrus.get_versions_path()).endswith(expected_out)


def test_get_versions_path_correctly_identifies_symlinked_location(
    tmp_path, monkeypatch, runcirrus
):
    script_path = (
        tmp_path / "cirrus/versions/.store/d312321-runcirrus-1.0.0/bin/runcirrus"
    )
    script_path.mkdir(parents=True)

    destination = tmp_path / "bin/runcirrus"
    destination.parent.mkdir()
    os.symlink(script_path, destination)

    def mockreturn(_):
        return destination

    monkeypatch.setattr(os.path, "dirname", mockreturn)
    assert str(runcirrus.get_versions_path()).endswith("")


def test_get_versions_path_correctly_fails(capsys, monkeypatch, runcirrus):
    def mockreturn(_):
        # the important thing is that "versions" does not exist in path
        return "/some/example/path"

    monkeypatch.setattr(os.path, "dirname", mockreturn)

    with pytest.raises(RuntimeError) as err:
        runcirrus.parse_args(["0", "--print-versions"])

    assert err.match("Not able to locate install location from /some/example/path")
