import os
import re
from pathlib import Path
import subprocess
import semver


DATADIR = Path(__file__).parent / "data"


def test_help() -> None:
    status = subprocess.run(["pflotran", "-help"], stdout=subprocess.PIPE)
    assert status.returncode == 87
    assert b"Options for all PETSc programs:" in status.stdout


def test_version() -> None:
    proc = subprocess.run(
        ["pflotran", "-pflotranin", "/dev/null"], stdout=subprocess.PIPE
    )

    match = re.search(r" Pflotran (\d+\.\d+sv\d+)\+\n", proc.stdout.decode())
    assert match, (
        f"Version not found in the following pflotran output: {proc.stdout.decode()}"
    )

    # Get the version as set by `deploy test`
    version = semver.Version.parse(os.environ["pflotran_version"])
    expected_version = f"{version.major}.{version.minor}sv{version.patch}"
    actual_version = match[1]

    assert expected_version == actual_version


def test_spe1(tmp_path, snapshot) -> None:
    output = subprocess.check_output(
        [
            "pflotran",
            "-pflotranin",
            DATADIR / "spe1.in",
            "-output_prefix",
            tmp_path / "spe1",
        ]
    )

    # Drop the first line which contains the Cirrus version
    output = output[output.find(b"\n") + 1 :]

    # Replace strings that change from run to run
    stdout = re.sub(
        r"(Pflotran was compiled on:|Run completed, wall clock time =).*",
        r"\1 [PRUNED]",
        output.decode(),
    )

    snapshot.assert_match(stdout, "stdout")
