from pathlib import Path
from deploy.builder import build_all
from deploy.context import Context


def test_context(context: Context) -> None:
    assert set(context.packages) == {"foo", "bar"}


def test_checkout(context: Context, tmp_path: Path) -> None:
    build_all(context)

    out = context.packages["foo"].out
    assert (out / "lib/libfoo.so").is_file()

    out = context.packages["bar"].out
    assert (out / "bin/bar").is_file()

    assert (
        context.run_sync(
            str(context["bar"].final_out / "bin/bar"),
        )
        == "I am a test\n"
    )
