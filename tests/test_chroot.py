from __future__ import annotations
import signal
import pytest
import os
from pathlib import Path
from deploy.chroot import Bind, BindNode, MkdirNode, chroot_call, merge_bindings


setup = {
    "/": Bind(exclude="prog"),
    "/prog/cirrus/versions/.store/petsc": Bind("results/petsc"),
    "/prog/cirrus/versions/.store/cirrus": Bind("results/cirrus", allow_writes=True),
}


def test_bind_none():
    assert merge_bindings({}) == MkdirNode()


def test_bind_root(monkeypatch):
    assert merge_bindings({"/": Bind()}) == BindNode("/")


def test_bind_single_dir(monkeypatch):
    assert merge_bindings({"/bin": Bind()}) == MkdirNode(children={"bin": BindNode()})


def test_bind_node_with_target():
    assert merge_bindings({"/": Bind(Path.cwd())}) == BindNode(target=Path.cwd())


def test_bind_node_exclude_with_target(monkeypatch):
    monkeypatch.setattr(os, "listdir", lambda _: ("bin", "etc", "usr"))

    assert merge_bindings({"/": Bind(Path.cwd(), exclude="bin")}) == MkdirNode(
        children={
            "etc": BindNode(target=Path.cwd() / "etc"),
            "usr": BindNode(target=Path.cwd() / "usr"),
        }
    )


@pytest.mark.parametrize(
    "reverse_setup",
    [pytest.param(False, id="normal"), pytest.param(True, id="reversed_setup")],
)
def test_bind_manual_exclude(monkeypatch, reverse_setup: bool):
    monkeypatch.setattr(os, "listdir", lambda _: ("bin", "etc", "usr"))

    setup = {"/bin": Bind(empty=True), "/": Bind()}

    if reverse_setup:
        setup = dict(reversed(setup.items()))

    assert merge_bindings(setup) == MkdirNode(
        children={"bin": MkdirNode(), "etc": BindNode(), "usr": BindNode()}
    )


def test_bind_exclude(monkeypatch):
    monkeypatch.setattr(os, "listdir", lambda _: ("bin", "etc", "usr"))

    assert merge_bindings({"/": Bind(exclude="etc")}) == MkdirNode(
        children={"bin": BindNode(), "usr": BindNode()}
    )


def test_bind_exclude_subdir(monkeypatch):
    monkeypatch.setattr(os, "listdir", lambda _: ("bin", "etc", "usr"))

    setup = {
        "/usr": Bind(exclude="usr"),
        "/": Bind(),
    }

    assert merge_bindings(setup) == MkdirNode(
        children={
            "bin": BindNode(),
            "etc": BindNode(),
            "usr": MkdirNode(children={"bin": BindNode(), "etc": BindNode()}),
        }
    )


def test_bind_subdir_empty(monkeypatch):
    def listdir(_):
        yield from ("bin", "usr")

    monkeypatch.setattr(os, "listdir", listdir)
    assert merge_bindings(
        {
            "/": Bind(),
            "/foo": Bind(empty=True),
        }
    ) == MkdirNode(children={"bin": BindNode(), "usr": BindNode(), "foo": MkdirNode()})


def test_bind_subsubdir_empty(monkeypatch):
    def listdir(_):
        yield from ("bin", "usr")

    monkeypatch.setattr(os, "listdir", listdir)
    assert merge_bindings(
        {
            "/": Bind(),
            "/foo/bar/quz": Bind(empty=True),
        }
    ) == MkdirNode(
        children={
            "bin": BindNode(),
            "usr": BindNode(),
            "foo": MkdirNode(
                children={"bar": MkdirNode(children={"quz": MkdirNode()})}
            ),
        }
    )


def test_chroot_python_call():
    """Test that chroot_call works even with an empty environment"""
    assert chroot_call({}, (lambda x: x + 1), 2) == 3


def test_chroot_exception():
    def raises():
        raise ValueError("Hello, world")

    with pytest.raises(ValueError, match="Hello, world"):
        chroot_call({}, raises)


def test_chroot_assert():
    def raises():
        assert False

    with pytest.raises(AssertionError, match="assert False"):
        chroot_call({}, raises)


def test_chroot_listdir(tmp_path: Path):
    def listdir() -> set[str]:
        return set(os.listdir("/"))

    name = "this-does-not-exist"
    (tmp_path / name).mkdir()
    inside = chroot_call({
        f"/{name}": Bind(tmp_path),
    }, listdir)

    # /proc is added automatically
    assert inside == {"proc", name}


def test_chroot_abort_exits_correctly():
    def silent_abort():
        # Override the SIGABRT handler so that Python doesn't write traceback
        _ = signal.signal(signal.SIGABRT, signal.SIG_IGN)
        os.abort()

    with pytest.raises(RuntimeError):
        chroot_call({}, silent_abort)


def test_chroot_files_created_outside_are_visible_inside(tmp_path: Path):
    name = "this-does-not-exist"
    _ = (tmp_path / "myfile").write_text("Heisann")

    def inner() -> str:
        return (Path("/") / name / "myfile").read_text()

    result = chroot_call({name: tmp_path}, inner)
    assert result == "Heisann"


def test_chroot_files_created_inside_are_visible_outside(tmp_path: Path):
    name = "this-does-not-exist"

    def inner() -> None:
        _ = (Path("/") / name / "myfile").write_text("Hoppsann")

    chroot_call({name: tmp_path}, inner)
    assert (tmp_path / "myfile").read_text() == "Hoppsann"
