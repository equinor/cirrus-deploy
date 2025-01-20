import re
from pathlib import Path
from subprocess import check_output


DATADIR = Path(__file__).parent / "data"


def test_help() -> None:
    output = check_output(["cirrus", "-help"])
    assert b"Cirrus command line options:" in output


def test_spe1(tmp_path, snapshot) -> None:
    output = check_output(
        [
            "cirrus",
            "-cirrusin",
            DATADIR / "spe1.in",
            "-output_prefix",
            tmp_path / "spe1",
        ]
    )

    # Drop the first line which contains the Cirrus version
    output = output[output.find(b"\n") + 1 :]

    # Replace strings that change from run to run
    stdout = re.sub(
        r"(Cirrus was compiled on:|Run completed, wall clock time =).*",
        r"\1 [PRUNED]",
        output.decode(),
    )

    snapshot.assert_match(stdout, "stdout")
