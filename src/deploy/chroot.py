from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import pickle
import shutil
import subprocess
import sys
import os
from pathlib import Path
from tempfile import mkdtemp
from traceback import print_exc, print_exception
from typing import Any, Callable, ParamSpec, TypeVar, cast
from collections.abc import Iterable, Mapping
import ctypes
from typing_extensions import override


__all__ = [
    "chroot_call",
    "chroot_run",
    "Bind",
]


libc = ctypes.CDLL(None, use_errno=True)

# $ man 2 unshare
# int unshare(int flags);
libc.unshare.restype = ctypes.c_int
libc.unshare.argtypes = (ctypes.c_int,)

# $ man 2 mount
# int mount(const char *source, const char *target,
#           const char *filesystemtype, unsigned long mountflags,
#           const void *_Nullable data);
libc.mount.restype = ctypes.c_int
libc.mount.argtypes = (
    ctypes.c_char_p,
    ctypes.c_char_p,
    ctypes.c_char_p,
    ctypes.c_ulong,
    ctypes.c_void_p,
)


# From /usr/include/linux/sched.h
CLONE_NEWNS = 0x00020000
CLONE_NEWUSER = 0x10000000


# From /usr/include/linux/mount.h
MS_RDONLY = 1
MS_BIND = 4096
MS_REC = 16384
MS_PRIVATE = 1 << 18


_P = ParamSpec("_P")
_T = TypeVar("_T")


@dataclass
class Bind:
    host_path: str | Path | None = None
    allow_writes: bool = False
    empty: bool = False
    parents: bool = False
    exclude: str | Iterable[str] | None = None


class PathNode(ABC):
    def __init__(self, *, children: dict[str, PathNode] | None = None) -> None:
        self.children: dict[str, PathNode] = children or {}

    @override
    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return self.children == other.children

    @override
    def __repr__(self) -> str:
        children = ", ".join(f"{repr(k)}: {repr(v)}" for k, v in self.children.items())
        return f"{self.__class__.__name__}({children})"

    @abstractmethod
    def validate(self, current_dir: Path) -> None:
        pass

    @abstractmethod
    def pre_mount(self, chroot_dir: Path, current_dir: Path) -> None:
        pass

    @abstractmethod
    def mount(self, chroot_dir: Path, current_dir: Path) -> None:
        pass

    @abstractmethod
    def post_mount(self, chroot_dir: Path, current_dir: Path) -> None:
        pass

    def validate_all(self, current_dir: Path | None = None) -> None:
        if current_dir is None:
            current_dir = Path()

        self.validate(current_dir)
        for name, child in self.children.items():
            child.validate_all(current_dir / name)

    def pre_mount_all(self, chroot_dir: Path, current_dir: Path | None = None) -> None:
        if current_dir is None:
            current_dir = Path()

        self.pre_mount(chroot_dir, current_dir)
        for name, child in self.children.items():
            child.pre_mount_all(chroot_dir, current_dir / name)

    def mount_all(self, chroot_dir: Path, current_dir: Path | None = None) -> None:
        if current_dir is None:
            current_dir = Path()

        for name, child in self.children.items():
            child.mount_all(chroot_dir, current_dir / name)
        self.mount(chroot_dir, current_dir)

    def post_mount_all(self, chroot_dir: Path, current_dir: Path | None = None) -> None:
        if current_dir is None:
            current_dir = Path()

        self.post_mount(chroot_dir, current_dir)
        for name, child in self.children.items():
            child.post_mount_all(chroot_dir, current_dir / name)


def mount_all(node: PathNode, chroot_dir: Path) -> None:
    from queue import Queue
    q: Queue[tuple[Path, PathNode]] = Queue()
    q.put((Path(), node))

    reverse_order: list[tuple[Path, PathNode]] = []

    while not q.empty():
        path, node = q.get()
        if isinstance(node, BindNode):
            reverse_order.append((path, node))
        if isinstance(node, MkdirNode):
            for name, child in node.children.items():
                q.put((path / name, child))

    for path, node in reversed(reverse_order):
        node.mount(chroot_dir, path)


class MkdirNode(PathNode):
    @override
    def validate(self, current_dir: Path) -> None:
        pass

    @override
    def pre_mount(self, chroot_dir: Path, current_dir: Path) -> None:
        if current_dir == Path(""):
            return

    @override
    def mount(self, chroot_dir: Path, current_dir: Path) -> None:
        pass

    @override
    def post_mount(self, chroot_dir: Path, current_dir: Path) -> None:
        pass


class BindNode(PathNode):
    def __init__(
        self,
        target: Path,
        *,
        children: dict[str, PathNode] | None = None,
        allow_writes: bool = False,
    ):
        super().__init__(children=children)
        self.source: Path = target
        self.allow_writes: bool = allow_writes

    @override
    def __eq__(self, other: Any) -> bool:
        return super().__eq__(other) and str(self.source) == str(other.target)

    @override
    def __repr__(self) -> str:
        children = ", ".join(f"{repr(k)}: {repr(v)}" for k, v in self.children.items())
        return f"{self.__class__.__name__}[{self.source}]({children})"

    @override
    def validate(self, current_dir: Path) -> None:
        if not self.source.exists():
            raise ValueError(f"{self.source} can't be bound because it doesn't exist")

    @override
    def pre_mount(self, chroot_dir: Path, current_dir: Path) -> None:
        source = chroot_dir / current_dir

        source.mkdir()

    @override
    def mount(self, chroot_dir: Path, current_dir: Path) -> None:
        source = self.source
        target = chroot_dir / current_dir

        mount_flags = MS_BIND | MS_REC | MS_PRIVATE
        if not self.allow_writes:
            mount_flags |= MS_RDONLY

        if source.is_symlink() or source.is_file():
            return
        target.mkdir(parents=True, exist_ok=True)
        if (
            libc.mount(
                bytes(source),
                bytes(target),
                b"none",
                mount_flags,
                None,
            )
            != 0
        ):
            sys.exit(
                f"Could not mount {source} to {target}: {os.strerror(ctypes.get_errno())}"
            )

    @override
    def post_mount(self, chroot_dir: Path, current_dir: Path) -> None:
        pass


def merge_bindings(mapping: Mapping[str, Bind]) -> PathNode:
    # The user requested a completely empty chroot
    if not mapping:
        return MkdirNode()

    # Handle the edge case of just a single mapping that is the root binding
    if len(mapping) == 1 and (r := mapping.get("/")) is not None and r.exclude is None:
        return BindNode(Path(r.host_path or Path("/")), allow_writes=r.allow_writes)

    root: PathNode = MkdirNode()

    for path, params in mapping.items():
        parts = Path(path).parts
        prev_node: PathNode = root
        current_dir = Path("/")
        for index, part in enumerate(parts):
            node: PathNode | None = prev_node.children.get(part)
            current_dir /= part

            # Non-leaf part of the path
            if index + 1 < len(parts):
                if isinstance(node, BindNode):
                    # Split up a BindNode into sub-BindNodes
                    children = {
                        name: BindNode(node.source / name)
                        for name in os.listdir(node.source)
                    }

                    node = MkdirNode(children=children)
                elif node is None:
                    node = MkdirNode()

            # Leaf part
            else:
                children: dict[str, PathNode] = {}
                if params.exclude is not None:
                    target = Path(params.host_path) if params.host_path else Path("/") / current_dir
                    if isinstance(node, BindNode):
                        target = node.source
                    children.update(
                        {
                            name: BindNode(target / name)
                            for name in os.listdir(target)
                            if name not in (params.exclude or [])
                        }
                    )
                if node is not None:
                    children.update(node.children)

                if params.empty:
                    node = MkdirNode()
                elif children:
                    node = MkdirNode(children=children)
                else:
                    node = BindNode(Path(params.host_path or Path("/") / current_dir))

            assert node is not None
            prev_node.children[part] = node
            prev_node = node

    return root.children["/"]


def chroot_call(
    mapping: Mapping[str, Bind],
    func: Callable[_P, _T],
    *args: _P.args,
    **kwargs: _P.kwargs,
) -> _T:
    tree = merge_bindings({**mapping, "/proc": Bind()})
    tree.validate_all(Path("/"))

    chroot_dir = Path(mkdtemp(prefix="deploy-chroot-"))

    fd_rd, fd_wr = os.pipe()
    rd = os.fdopen(fd_rd, "rb")
    wr = os.fdopen(fd_wr, "wb")

    # In case we are the parent, wait for child to finish and exit
    if (pid := os.fork()) != 0:
        try:
            _, status = os.waitpid(pid, os.WUNTRACED)
            if status != 0:
                raise RuntimeError(
                    f"chroot_func: subprocess exited with status {status}"
                )
            is_exc, result = cast(tuple[bool, Any], pickle.load(rd))
            if is_exc:
                raise result
            return cast(_T, result)
        finally:
            shutil.rmtree(chroot_dir)
            rd.close()

    # The following happens only inside the child process
    try:
        cwd = os.getcwd()
        uid = os.getuid()
        gid = os.getgid()

        if libc.unshare(CLONE_NEWNS | CLONE_NEWUSER) != 0:
            sys.exit(f"Could not unshare: {os.strerror(ctypes.get_errno())}")

        mount_all(tree, chroot_dir)

        os.chroot(chroot_dir)

        _ = Path("/proc/self/setgroups").write_text("deny")
        _ = Path("/proc/self/uid_map").write_text(f"{uid} {uid} 1")
        _ = Path("/proc/self/gid_map").write_text(f"{gid} {gid} 1")
        pickle.dump((False, func(*args, **kwargs)), wr)
    except BaseException as exc:
        print_exception(exc)
        pickle.dump((True, exc), wr)
    finally:
        wr.close()
        os._exit(0)


def chroot_run(
    setup: Mapping[str, Path],
    program: str | Path,
    *args: str | Path,
) -> subprocess.CompletedProcess[bytes]:
    return chroot_call(setup, subprocess.run, [program, *args])
