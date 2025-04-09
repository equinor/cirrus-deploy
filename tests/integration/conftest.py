from __future__ import annotations
import os
from pathlib import Path
from deploy.build import Build
from deploy.config import Config
import pytest
import subprocess
import shutil


DIR = Path(os.path.dirname(__file__))


class Git:
    def __init__(self, path: Path, initial_commit: Path | None = None) -> None:
        self.path: Path = path

        if initial_commit:
            self.initial_commit(initial_commit)

    def initial_commit(self, file: Path) -> None:
        shutil.copy(file, self.path / file.name)

        self("init", "-b", "main")
        self("config", "user.email", "user@example.com")
        self("config", "user.name", "Ola Nordmann")
        self("add", file.name)
        self("commit", "-m", "Initial commit")

    def __call__(self, *args: str | Path) -> str:
        return subprocess.check_output(["git", *args], cwd=self.path).decode("utf-8")

    @property
    def ref(self) -> str:
        return self("rev-parse", "HEAD").strip()


@pytest.fixture(scope="session")
def git_foo(tmp_path_factory: pytest.TempPathFactory) -> Git:
    tmp_path = tmp_path_factory.mktemp("foo.git")
    return Git(tmp_path, DIR / "data/foo.c")


@pytest.fixture(scope="session")
def git_bar(tmp_path_factory: pytest.TempPathFactory) -> Git:
    tmp_path = tmp_path_factory.mktemp("bar.git")
    return Git(tmp_path, DIR / "data/bar.c")


@pytest.fixture()
def config(tmp_path: Path, git_foo: Git, git_bar: Git) -> Config:
    foo_config = {
        "name": "foo",
        "version": "1.2.3",
        "src": {
            "type": "git",
            "url": f"file://{git_foo.path}",
            "ref": git_foo.ref,
        },
    }

    bar_config = {
        "name": "bar",
        "version": "3.2.1",
        "src": {
            "type": "git",
            "url": f"file://{git_bar.path}",
            "ref": git_bar.ref,
        },
        "depends": ["foo"],
    }

    base_config = {
        "paths": {
            "store": "versions/.store",
        },
        "builds": [foo_config, bar_config],
        "envs": [],
        "links": {},
    }

    return Config.model_validate(base_config)


@pytest.fixture
def build(tmp_path: Path, config: Config) -> Build:
    return Build(
        Path("/dev/null"),
        config,
        force=False,
        extra_scripts=DIR / "data/scripts",
        prefix=tmp_path / "output",
    )
