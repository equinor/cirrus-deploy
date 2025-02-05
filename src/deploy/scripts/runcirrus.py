#!/usr/bin/python3.11
"""Wrapper for running Cirrus with MPI in Equinor.

This script operates on Cirrus .in files and enables you to simulate in
parallell. For example, given the "spe1.in" case, you can simply run it with the
following command:

    $ runcirrus spe1.in

This will use all available cores on your local machine, and output the
following files:

    'spe1.out': Text summarising the simulation
    'spe1-mas.dat':
    'spe1.INIT':
    'spe1.SMSPEC':
    'spe1.UNSMRY':

Additionally, runcirrus produces the following files:

    'spe1.LOG': Cirrus' "stdout" standard output
    'spe1.ERR': Cirrus' "stderr" standard error
    'spe1_bsub.LOG': Logs from the workflow manager when using IBM LSF

To utilise the HPC cluster, specify '-q' (aka. '--queue'). In this
configuration, only 1 CPU will be utilised by default. To change this behaviour,
use the '-n' and '-m' options. '-n' is "number of tasks per machine" and '-m' is
"number of machines".

For example, to add a job to the 'bigmem' queue using 2 machines (nodes) and 8
processes per machine for a total of 16 cores, use:

    $ runcirrus -q bigmem -n 8 -m 2 spe1.in

"""

from __future__ import annotations
import sys
from typing import Any, NoReturn
import os
import argparse
import shutil
import shlex
import re
import socket
from pathlib import Path
from dataclasses import dataclass
from time import time


EVENT_NAMESPACE = ""
EVENT_HUB = ""
SAS_KEY_NAME = ""
SAS_KEY_VALUE = b""


def az_create_sas_token(uri: str) -> str:
    """Create SAS token to be able to interact with the Event Hub"""
    import hmac
    import urllib.parse
    import base64

    ttl = time() + 86400

    quri = urllib.parse.quote_plus(uri)

    sign_key = f"{quri}\n{int(ttl)}".encode("utf-8")
    signature = base64.b64encode(
        hmac.new(SAS_KEY_VALUE, sign_key, "sha256").digest()
    ).decode("utf-8")
    qsig = urllib.parse.quote(signature)
    token = (
        f"SharedAccessSignature sr={quri}&sig={qsig}&se={int(ttl)}&skn={SAS_KEY_NAME}"
    )
    return token


def az_send_event(data: dict[str, Any]) -> None:
    """Send data to Microsoft Azure Event Hub"""
    if not all([EVENT_NAMESPACE, EVENT_HUB, SAS_KEY_NAME, SAS_KEY_VALUE]):
        return

    import http.client
    import json

    uri = f"https://{EVENT_NAMESPACE}.servicebus.windows.net/{EVENT_HUB}/messages"
    body = json.dumps(data)
    headers = {
        "Authorization": az_create_sas_token(uri),
        "Content-Length": str(len(body)),
        "Content-Type": "application/json",
    }

    conn = http.client.HTTPSConnection(f"{EVENT_NAMESPACE}.servicebus.windows.net")
    conn.request("POST", f"/{EVENT_HUB}/messages", body=body, headers=headers)

    if (resp := conn.getresponse()) and resp.status != 201:
        print("Failure during logging:", file=sys.stderr)
        print(f"HTTP Status: {resp.status} ({resp.reason})", file=sys.stderr)
        print(resp.read(), file=sys.stderr)

    conn.close()


def anonymize_fqdn(fqdn: str) -> str:
    """Anonymize fully-qualified domain name"""

    index = fqdn.find(".")
    return "" if index < 0 else fqdn[index:]


SCRIPT = """\
#!/usr/bin/bash
set -e -o pipefail

cd "{outdir}"

arg_mpi_transport=
arg_machinefile=

if [ -n "$LSB_MCPU_HOSTS" ]; then  # LSF
    arg_machinefile="-machinefile $LSB_DJOB_RANKFILE"
elif [ -n "$PBS_NODEFILE" ]; then  # PBS
    arg_machinefile="-machinefile $PBS_NODEFILE"
fi

# Check for possibly non-working RDMA transport
if lsmod | egrep -qw bnxt_re
then
    arg_mpi_transport="-mca btl vader,self,tcp -mca pml ^ucx"
fi

({root}/bin/mpirun $arg_mpi_transport $arg_machinefile {num_tasks} {mpi_args} {telemetry} {root}/bin/{progname} {cirrus_args} -{progname}in "{input_file}" -output_prefix "{outdir}/{case}" | tee "{outdir}/{case}.LOG") 3>&1 1>&2 2>&3 | tee "{outdir}/{case}.ERR"
"""


HAVE_BSUB = shutil.which("bsub") is not None  # IBM LSF
HAVE_QSUB = shutil.which("qsub") is not None  # OpenPBS


def default_version(script_name: str) -> str:
    """Determine the default version from script name"""
    p = re.compile(r"^run(cirrus|pflotran)(\d+(?:\.\d+)*)?")
    if (m := p.match(script_name)) is None:
        return "stable"
    if v := m.group(2):
        return v
    if m.group(1) == "pflotran":
        return "1.8"
    return "stable"


def ensure_local_on_hpc(args: Arguments) -> None:
    """
    If we're running on the cluster alrea, override queue to local and set
    num tasks to 1.
    """
    if args.queue != "local" and any(
        x in os.environ for x in ("LSB_DJOB_RANKFILE", "PBS_NODEFILE")
    ):
        args.queue = "local"
        args.num_tasks_per_machine = args.num_tasks_per_machine or 1


def get_versions_path() -> Path:
    """Get directory path of install cirrus versions

    Use CIRRUS_VERSIONS_PATH environment variable to determine where we are, or
    if unset, use "versions" directory next to the location of this script.

    """
    if (path := os.environ.get("CIRRUS_VERSIONS_PATH")) is not None:
        return Path(path)

    search_path = Path(os.path.dirname(__file__)).resolve()

    while search_path.name != "versions":
        search_path = search_path.parent

        if search_path.parent == search_path:
            # Hit root
            raise RuntimeError(
                f"Not able to locate install location from {Path(os.path.dirname(__file__))}"
            )

    return search_path


class PrintVersionAction(argparse.Action):
    def __call__(self, *_args: Any) -> None:
        possible_versions = []

        for fpath in os.listdir(get_versions_path()):
            if fpath.startswith("."):
                continue

            possible_versions.append(fpath)

        if not possible_versions:
            print(f"No installed versions found at {get_versions_path()}")
        else:
            print("\n".join(possible_versions))

        sys.exit()


@dataclass
class Arguments:
    input: str
    queue: str
    num_tasks_per_machine: int
    num_machines: int
    version: str
    print_job_script: bool
    print_versions: bool
    mpi_args: str
    cirrus_args: str
    output_directory: str | None
    interactive: bool

    telemetry: str | None = None
    bsub_args: str | None = None
    qsub_args: str | None = None
    exclusive: bool | None = None


def parse_args(argv: list[str]) -> Arguments:
    ap = argparse.ArgumentParser(
        prog="runcirrus",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("input", help="Cirrus .in input file")
    ap.add_argument(
        "-q", "--queue", default="local", help="Job queue, or 'local' to run locally"
    )
    ap.add_argument(
        "-n",
        "--num-tasks-per-machine",
        type=int,
        help="Number of tasks/processes per machine",
    )
    ap.add_argument(
        "-m",
        "--num-machines",
        default=1,
        type=int,
        help="Number of machines (nodes)",
    )
    ap.add_argument("-i", "--interactive", action="store_true", help="Run locally")
    ap.add_argument(
        "-v",
        "--version",
        help="Version of Cirrus to use",
    )
    ap.add_argument(
        "-o",
        "--output-directory",
        help="Directory to store the output to",
    )
    ap.add_argument(
        "--cirrus-args",
        help="Additional arguments for Cirrus",
    )
    ap.add_argument(
        "--mpi-args",
        help="Additional arguments for mpirun command",
    )
    ap.add_argument(
        "--telemetry",
        type=str,
        default="",
        help="Program to run between mpirun and Cirrus",
    )
    if HAVE_BSUB:
        ap.add_argument("--bsub-args", help="Additional arguments for bsub command")
    if HAVE_QSUB:
        ap.add_argument("--qsub-args", help="Additional arguments for qsub command")
        ap.add_argument(
            "-e", "--exclusive", help="Exclusive node usage [default: shared]"
        )
    ap.add_argument(
        "--print-job-script",
        action="store_true",
        help="Output job script and exit",
    )
    ap.add_argument(
        "--print-versions",
        action=PrintVersionAction,
        nargs=0,
        help="Output Cirrus versions and exit",
    )
    return Arguments(**vars(ap.parse_args(argv[1:])))


def run(program: str, *args: str) -> NoReturn:
    print(f"{program} {shlex.join(args[:-1])} <SCRIPT>")
    os.execvp(program, [program, *args])


def run_local(script: str, args: Arguments) -> NoReturn:
    run(
        "bash",
        "-c",
        script,
    )


def run_bsub(script: str, args: Arguments, input_file: Path) -> NoReturn:
    num_tasks = args.num_machines * args.num_tasks_per_machine

    resources = ["select[rhel >= 8]", "same[type:model]"]
    resources.append(f"span[ptile={args.num_tasks_per_machine}]")
    resource_string = " ".join(resources)

    user_args = shlex.split(args.bsub_args or "")

    script_path = input_file.parent / f"{input_file.stem}.run"
    script_path.write_text(script, encoding="utf-8")

    run(
        "bsub",
        "-q",
        args.queue,
        "-n",
        str(num_tasks),
        "-o",
        f"{input_file.parent}/{input_file.stem}_bsub.LOG",
        "-J",
        f"Cirrus_{input_file.name}",
        "-R",
        resource_string,
        *user_args,
        "--",
        "bash",
        str(script_path),
    )


def run_qsub(script: str, args: Arguments, input_file: Path) -> NoReturn:
    place = "scatter:excl" if args.exclusive else "scatter:shared"

    user_args = shlex.split(args.qsub_args or "")

    script_path = input_file.parent / f"{input_file.stem}.run"
    script_path.write_text(script, encoding="utf-8")

    run(
        "qsub",
        "-q",
        args.queue,
        "-l",
        f"select={args.num_machines}:ncpus={args.num_tasks_per_machine}:mpiprocs={args.num_tasks_per_machine}",
        "-l",
        f"place={place}",
        "-j",
        "oe",
        "-o",
        f"{input_file.parent}/{input_file.stem}_qsub.LOG",
        "-N",
        f"Cirrus_{input_file.name}",
        *user_args,
        "--",
        "/usr/bin/bash",
        "-c",
        script,
    )


def main() -> None:
    argv = []
    for arg in sys.argv:
        if arg == "-nn":
            argv.append("-m")
        elif arg == "-nm":
            argv.append("-n")
        else:
            argv.append(arg)

    args = parse_args(argv)
    input_file = Path(args.input).resolve()
    if not input_file.exists():
        sys.exit(f"Cirrus input file '{input_file}' does not exit!")

    if args.interactive:
        args.queue = "local"

    ensure_local_on_hpc(args)

    if args.num_tasks_per_machine is None:
        if args.queue != "local":
            sys.exit(
                "Must specify -n/--num-tasks-per-machine when running on a non-local queue"
            )
        args.num_tasks_per_machine = os.cpu_count() or 1
    if args.num_machines > 1 and args.queue == "local":
        sys.exit(
            "Must specify -q/--queue when attempting to run on multiple machines with -m/--num-machines"
        )

    version = default_version(os.path.basename(sys.argv[0]))
    if args.version:
        version = args.version

    for versions_path in get_versions_path(), Path("/prog/cirrus/versions"):
        rootdir = (versions_path / version).resolve()
        if rootdir.exists():
            break
    else:
        sys.exit(f"Cirrus version '{version}' is not installed in {versions_path}")

    progname = "cirrus"
    if version and version.split(".") < ["1", "9"]:
        progname = "pflotran"

    num_tasks = args.num_machines * args.num_tasks_per_machine

    if args.output_directory:
        outdir = Path(args.output_directory)
    else:
        outdir = Path(args.input).parent

    script = SCRIPT.format(
        root=rootdir,
        workdir=input_file.parent,
        input_file=input_file,
        case=input_file.stem,
        progname=progname,
        mpi_args=args.mpi_args or "",
        cirrus_args=args.cirrus_args or "",
        num_tasks=f"-np {num_tasks}" if num_tasks is not None else "",
        outdir=outdir.resolve(),
        telemetry=args.telemetry,
    )

    az_send_event(
        {
            "type": "runcirrus",
            "script": sys.argv[0],
            "version": args.version,
            "num_tasks_per_machine": args.num_tasks_per_machine,
            "num_machines": args.num_machines,
            "num_tasks": num_tasks,
            "queue": args.queue,
            "bsub": HAVE_BSUB,
            "qsub": HAVE_QSUB,
            "hostname": anonymize_fqdn(socket.getfqdn()),
        }
    )

    if args.print_job_script:
        print(script)
    elif args.queue == "local":
        run_local(script, args)
    elif HAVE_BSUB:
        run_bsub(script, args, input_file)
    elif HAVE_QSUB:
        run_qsub(script, args, input_file)
    else:
        sys.exit("No supported job scheduler detected on this machine")


if __name__ == "__main__":
    main()
