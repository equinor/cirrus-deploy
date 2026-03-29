from __future__ import annotations
import os
from pathlib import Path
import subprocess

from karsk.config import GitConfig
from karsk.package import Package


def git_checkout(pkg: Package) -> None:
    if not isinstance(gitconf := pkg.config.src, GitConfig) or pkg.src is None:
        return

    env = os.environ.copy()

    if gitconf.ssh_key_path is not None:
        env["GIT_SSH_COMMAND"] = (
            f"{os.environ.get('GIT_SSH_COMMAND', 'ssh')} -i {gitconf.ssh_key_path.absolute()}"
        )

    def git(*args: str | Path) -> None:
        subprocess.run(("git", *args), check=True, cwd=pkg.src, env=env)

    try:
        pkg.src.mkdir(parents=True)
    except FileExistsError:
        git("reset", "--hard")
        git("clean", "-xdf")
        return

    git("init", "-b", "main")
    git("remote", "add", "origin", gitconf.url)
    git("fetch", "origin", gitconf.ref)
    git("checkout", "FETCH_HEAD")
