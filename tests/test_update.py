import io
from typing import Any
import pytest
import deploy.update
from deploy.update import GitHubBranch
import yaml


DEFAULT_COMMIT_SHA = ""


class _Responder:
    def __init__(self):
        self.response = {
            "name": "main",
            "commit": {
                "sha": "123",
                "commit": {
                    "author": {
                        "name": "Test",
                        "email": "test@example.com",
                    },
                    "committer": {
                        "name": "Test",
                        "email": "test@example.com",
                    },
                    "message": "Fake commit",
                }
            }
        }

    def __call__(self, *args) -> GitHubBranch:
        return GitHubBranch.model_validate(self.response)


@pytest.fixture
def gh_api_response(monkeypatch: pytest.MonkeyPatch) -> _Responder:
    responder = _Responder()
    monkeypatch.setattr(deploy.update, "get_branch_info", responder)

    return responder


@pytest.fixture
def config(base_config):
    base_config["builds"].append(
        {
            "name": "mypkg",
            "version": "1.0.0",
            "depends": [],
            "src": {
                "type": "github",
                "owner": "foo",
                "repo": "bar",
                "ref": "123",
            },
        }
    )
    return base_config


def test_no_difference(config, gh_api_response) -> None:
    content = yaml.safe_dump(config)

    assert content == deploy.update.update_config(content, "mypkg", "main", "1.0.0")


def test_update(config, gh_api_response) -> None:
    content = yaml.safe_dump(config)

    gh_api_response.response["commit"]["sha"] = "TESTSHA"

    assert "TESTSHA" in deploy.update.update_config(content, "mypkg", "main", None)
