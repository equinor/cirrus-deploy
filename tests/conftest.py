import pytest


@pytest.fixture(autouse=True)
def set_cache_path(tmp_path, monkeypatch):
    import deploy.package

    cachepath = tmp_path / ".cache"
    cachepath.mkdir()
    monkeypatch.setattr(deploy.package, "get_cache_path", lambda: cachepath)


@pytest.fixture
def base_config():
    return {
        "paths": {"store": ".store"},
        "builds": [],
        "envs": [],
        "areas": [],
        "links": {},
    }
