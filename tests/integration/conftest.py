from __future__ import annotations
import os
from pathlib import Path
from karsk.config import Config
import pytest
import subprocess
import shutil

from karsk.context import Context


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


FOO_BUILD = """
mkdir $out/lib
cc -shared -fPIC -o $out/lib/libfoo.so $src/foo.c
"""


BAR_BUILD = """
mkdir $out/bin
cc -o $out/bin/bar $src/bar.c -L$foo/lib -lfoo -Wl,-rpath,$foo/lib
"""


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
        "build": FOO_BUILD,
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
        "build": BAR_BUILD,
    }

    base_config = {
        "destination": "/opt/karsk/test",
        "main-package": "bar",
        "build-image": os.path.join(os.path.dirname(__file__), "Containerfile"),
        "entrypoints": [],
        "packages": [foo_config, bar_config],
        "links": {},
    }

    return Config.model_validate(base_config)


@pytest.fixture
def context(tmp_path: Path, config: Config) -> Context:
    return Context(config, staging=tmp_path)
