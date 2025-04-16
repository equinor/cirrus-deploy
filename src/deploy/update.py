from datetime import datetime
from subprocess import check_output
import sys
from typing_extensions import override
from deploy.config import Config, GitHubConfig
from pydantic import BaseModel
import yaml


class GitHubAuthor(BaseModel):
    name: str
    email: str

    @override
    def __str__(self) -> str:
        return f"{self.name} <{self.email}>"


class GitHubCommitInfo(BaseModel):
    author: GitHubAuthor
    committer: GitHubAuthor
    message: str

    @override
    def __str__(self) -> str:
        return (
            f"Message: {self.message}\n"
            f"Authored by: {self.author}\n"
            f"Committed by: {self.committer}"
        )


class GitHubCommit(BaseModel):
    sha: str
    commit: GitHubCommitInfo

    @override
    def __str__(self) -> str:
        return f"Commit {self.sha}\n{self.commit}"


class GitHubBranch(BaseModel):
    name: str
    commit: GitHubCommit


def do_update(config: Config, package: str, branch: str, new_version: str) -> None:
    for build in config.builds:
        if build.name == package:
            break
    else:
        sys.exit(
            f"Unknown package '{package}'. Must be one of: {', '.join(x.name for x in config.builds)}"
        )

    src = build.src
    assert src is not None
    if not isinstance(src, GitHubConfig):
        sys.exit(f"Don't know how to upgrade a '{src.type}' source")

    stdout = check_output(
        [
            "gh",
            "api",
            "-H",
            "Accept: application/vnd.github+json",
            "-H",
            "X-GitHub-Api-Version: 2022-11-28",
            f"/repos/{src.owner}/{src.repo}/branches/{branch}",
        ]
    )
    data = GitHubBranch.model_validate_json(stdout)

    print("Found commit:", file=sys.stderr)
    print(data.commit, file=sys.stderr)

    build.version = new_version
    src.ref = data.commit.sha

    yaml.dump(config.model_dump(), sys.stdout)
