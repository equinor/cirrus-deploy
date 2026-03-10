import pytest


@pytest.fixture(autouse=True)
def set_base_path(tmp_path, monkeypatch):
    import deploy.config

    cachepath = tmp_path / "karsk-base"
    cachepath.mkdir()
    monkeypatch.setattr(deploy.config, "get_default_output_path", lambda: cachepath)
