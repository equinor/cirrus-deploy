from unittest.mock import AsyncMock, patch

import pytest
import yaml
from click.testing import CliRunner

from karsk.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def config_file(tmp_path):
    containerfile = tmp_path / "Containerfile"
    containerfile.write_text("FROM scratch\n")

    config = {
        "destination": str(tmp_path / "dest"),
        "main-package": "hello",
        "entrypoint": "bin/hello",
        "build-image": str(containerfile),
        "packages": [
            {
                "name": "hello",
                "version": "1.0.0",
                "build": "mkdir -p $out/bin\n",
            }
        ],
    }

    path = tmp_path / "config.yaml"
    path.write_text(yaml.dump(config))
    return path


def test_cli_help(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0


def test_build_help(runner):
    result = runner.invoke(cli, ["build", "--help"])
    assert result.exit_code == 0


def test_enter_help(runner):
    result = runner.invoke(cli, ["enter", "--help"])
    assert result.exit_code == 0


def test_sync_help(runner):
    result = runner.invoke(cli, ["sync", "--help"])
    assert result.exit_code == 0


def test_test_help(runner):
    result = runner.invoke(cli, ["test", "--help"])
    assert result.exit_code == 0


def test_schema_help(runner):
    result = runner.invoke(cli, ["schema", "--help"])
    assert result.exit_code == 0


def test_schema_runs(runner):
    result = runner.invoke(cli, ["schema"])
    assert result.exit_code == 0


@patch("karsk.commands.build.build_all", new_callable=AsyncMock)
def test_build_accepts_args(mock_build, runner, config_file):
    result = runner.invoke(
        cli,
        [
            "build",
            str(config_file),
            "--staging",
            str(config_file.parent),
            "--engine",
            "native",
        ],
    )
    assert result.exit_code == 0, result.output
    mock_build.assert_called_once()


@patch("karsk.commands.sync.sync_all", new_callable=AsyncMock)
def test_sync_accepts_args(mock_sync, runner, config_file):
    result = runner.invoke(
        cli,
        ["sync", str(config_file), "--staging", str(config_file.parent), "--dry-run"],
    )
    assert result.exit_code == 0, result.output
    mock_sync.assert_called_once()


def test_enter_accepts_args(runner, config_file):
    result = runner.invoke(
        cli,
        ["enter", str(config_file), "--staging", str(config_file.parent), "--help"],
    )
    assert result.exit_code == 0


def test_init_help(runner):
    result = runner.invoke(cli, ["init", "--help"])
    assert result.exit_code == 0


def test_init_creates_project(runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(cli, ["init", "myproject"])
    assert result.exit_code == 0, result.output

    assert set(tmp_path.glob("**/*")) == {
        tmp_path / "myproject",
        tmp_path / "myproject/Containerfile",
        tmp_path / "myproject/config.yaml",
        tmp_path / "myproject/karsk_tests",
        tmp_path / "myproject/karsk_tests/test_version.py",
    }


def test_init_fails_if_directory_exists(runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "existing").mkdir()
    result = runner.invoke(cli, ["init", "existing"])
    assert result.exit_code != 0
    assert "Project directory isn't empty" in result.output
