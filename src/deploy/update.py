from difflib import unified_diff
import io
from pathlib import Path
from subprocess import check_output
import sys
from typing_extensions import override
from pydantic import BaseModel
from ruamel.yaml import YAML
from rich.prompt import Confirm
from rich.console import Console


console = Console()


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


def get_branch_info(owner: str, repo: str, branch: str) -> GitHubBranch:
    stdout = check_output(
        [
            "gh",
            "api",
            "-H",
            "Accept: application/vnd.github+json",
            "-H",
            "X-GitHub-Api-Version: 2022-11-28",
            f"/repos/{owner}/{repo}/branches/{branch}",
        ]
    )
    return GitHubBranch.model_validate_json(stdout)


def update_config(content: str, package: str, branch: str, version: str | None) -> str:
    yaml = YAML()
    config = yaml.load(io.StringIO(content))

    for build in config["builds"]:
        if build["name"] == package:
            break
    else:
        sys.exit(
            f"Unknown package '{package}'. Must be one of: {', '.join(x.name for x in config.builds)}"
        )

    src = build["src"]
    if src["type"] != "github":
        sys.exit(f"Don't know how to upgrade a '{src['type']}' source")

    data = get_branch_info(src["owner"], src["repo"], branch)

    print("Found commit:", file=sys.stderr)
    print(data.commit, file=sys.stderr)

    build["version"] = version
    src["ref"] = data.commit.sha

    updated_content = io.StringIO()
    yaml.dump(config, updated_content)
    return updated_content.getvalue()


def do_update(config_dir: Path, package: str, branch: str, version: str | None) -> None:
    config_path = config_dir / "config.yaml"

    yaml = YAML()
    with open(config_path) as f:
        config = yaml.load(f)

    for build in config["builds"]:
        if build["name"] == package:
            break
    else:
        sys.exit(
            f"Unknown package '{package}'. Must be one of: {', '.join(x.name for x in config.builds)}"
        )

    src = build["src"]
    if src["type"] != "github":
        sys.exit(f"Don't know how to upgrade a '{src['type']}' source")

    data = get_branch_info(src["owner"], src["repo"], branch)

    print("Found commit:", file=sys.stderr)
    print(data.commit, file=sys.stderr)

    pre = io.StringIO()
    yaml.dump(config, pre)

    build["version"] = version
    src["ref"] = data.commit.sha

    post = io.StringIO()
    yaml.dump(config, post)

    if pre.getvalue() == post.getvalue():
        print("Already newest version.", file=sys.stderr)
        sys.exit()

    sys.stderr.writelines(
        unified_diff(
            pre.getvalue().splitlines(True),
            post.getvalue().splitlines(True),
            fromfile="config.yaml",
            tofile="config.yaml",
        )
    )
    if Confirm.ask("Is this ok?"):
        config_path.write_text(post.getvalue())
