from asyncio.subprocess import PIPE
from karsk.context import Context


async def test_version_of_hello(karsk: Context):
    expected = karsk["hello"].config.version

    print(karsk.out("hello", staging=False))
    proc = await karsk.run(
        karsk.out("hello", staging=False) / "bin/binary.sh",
        "--version",
        stdout=PIPE,
    )
    stdout, _ = await proc.communicate()
    assert proc.returncode == 0
    assert expected in stdout.decode()
