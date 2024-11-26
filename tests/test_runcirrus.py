from src import runcirrus
import pytest


def test_printversions_empty_folder(capsys, tmp_path, monkeypatch):
    monkeypatch.setenv("CIRRUS_VERSIONS_PATH", str(tmp_path))
    with pytest.raises(SystemExit):
        runcirrus.parse_args(["0", "--print-versions"])

    assert capsys.readouterr().out == f"No installed versions found at {tmp_path}\n"


@pytest.mark.parametrize(
    "dirs,expected_out", [(["1.10"], "1.10\n"), (["1.10", ".store"], "1.10\n")]
)
def test_printversions_ignore_hidden(dirs, expected_out, capsys, tmp_path, monkeypatch):
    for name in dirs:
        (tmp_path / name).mkdir()
    monkeypatch.setenv("CIRRUS_VERSIONS_PATH", str(tmp_path))

    with pytest.raises(SystemExit):
        runcirrus.parse_args(["0", "--print-versions"])

    assert capsys.readouterr().out == expected_out
