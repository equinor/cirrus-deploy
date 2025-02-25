import subprocess
from deploy.build import Build


def test_build(build: Build) -> None:
    assert set(build.packages) == {"foo", "bar"}


def test_checkout(build: Build) -> None:
    build.build()

    out = build.packages["foo"].out
    assert (out / "lib/libfoo.so").is_file()

    out = build.packages["bar"].out
    assert (out / "bin/bar").is_file()

    assert subprocess.check_output([out / "bin/bar"]) == b"I am a test\n"
