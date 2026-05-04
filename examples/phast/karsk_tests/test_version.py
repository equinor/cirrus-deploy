from asyncio.subprocess import PIPE

from karsk.context import Context


async def test_version_of_phast(karsk: Context):
    expected = karsk["phast"].config.version

    proc = await karsk.run(
        karsk.out("phast", staging=False) / "bin/phast",
        "--version",
        stdout=PIPE,
    )
    stdout, _ = await proc.communicate()
    assert proc.returncode == 0
    assert expected in stdout.decode()
