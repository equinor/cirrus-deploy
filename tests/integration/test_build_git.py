from asyncio.subprocess import PIPE
from pathlib import Path
from karsk.builder import build_all
from karsk.context import Context


def test_context(context: Context) -> None:
    assert set(context.packages) == {"foo", "bar"}


async def test_checkout(context: Context, tmp_path: Path) -> None:
    await build_all(context)

    assert (context.out("foo") / "lib/libfoo.so").is_file()
    assert (context.out("bar") / "bin/bar").is_file()

    proc = await context.run(
        str(context.out("bar", staging=False) / "bin/bar"), stdout=PIPE
    )
    await proc.wait()

    stdout = await proc.stdout.read()
    assert stdout == b"I am a test\n"
