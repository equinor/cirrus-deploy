#!/usr/bin/python3.11
from __future__ import annotations
import sys
from typing import Any, NoReturn
import os
import argparse
import shutil
import shlex
import re
from pathlib import Path
from dataclasses import dataclass


SCRIPT = """\
#!/usr/bin/bash
set -e

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
        args.num_tasks = args.num_tasks or 1


def get_versions_path() -> Path:
    """Get directory path of install cirrus versions

    Use CIRRUS_VERSIONS_PATH environment variable to determine where we are, or
    if unset, use "versions" directory next to the location of this script.

    """
    if (path := os.environ.get("CIRRUS_VERSIONS_PATH")) is not None:
        return Path(path)

    return Path(os.path.dirname(__file__)).parent / "versions"


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
    num_tasks_per_node: int
    num_nodes: int
    num_tasks: int | None
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
        description="Wrapper for running Cirrus with MPI in Equinor"
    )
    ap.add_argument("input", help="Cirrus .in input file")
    ap.add_argument(
        "-q", "--queue", default="local", help="Job queue, or 'local' to run locally"
    )
    ap.add_argument(
        "-n",
        "--num-tasks",
        type=int,
        help="Number of tasks/processes to use",
    )
    ap.add_argument(
        "-N",
        "--num-nodes",
        type=int,
        help="Number of nodes",
    )
    ap.add_argument("-i", "--interactive", action="store_true", help="Run locally")
    ap.add_argument(
        "-M",
        "--num-tasks-per-node",
        type=int,
        help="Number of tasks/processes per node",
    )
    ap.add_argument(
        "-v",
        "--version",
        default=os.environ.get("CIRRUS_VERSION", "latest"),
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
    num_tasks = args.num_tasks or args.num_nodes * args.num_tasks_per_node

    resources = ["select[rhel >= 8]", "same[type:model]"]
    if args.num_tasks_per_node:
        resources.append(f"span[ptile={args.num_tasks_per_node}]")
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
        f"select={args.num_nodes}:ncpus={args.num_tasks_per_node}:mpiprocs={args.num_tasks_per_node}",
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
            argv.append("-N")
        elif arg == "-nm":
            argv.append("-M")
        else:
            argv.append(arg)

    args = parse_args(argv)
    input_file = Path(args.input).resolve()
    if not input_file.exists():
        sys.exit(f"Cirrus input file '{input_file}' does not exit!")

    if args.interactive:
        args.queue = "local"

    if args.num_nodes and not args.num_tasks_per_node:
        sys.exit(
            "When specifying -N/--num-nodes, you must also specify -M/--num-tasks-per-node"
        )
    if args.num_tasks_per_node and not args.num_nodes:
        args.num_nodes = 1
    if args.num_nodes and args.num_tasks:
        sys.exit("Specify exactly one of -n/--num-tasks or -N/--num-nodes")
    if args.queue != "local" and not (args.num_tasks or args.num_nodes):
        sys.exit(
            "When queue is non-local, you must set -n/--num-tasks or -N/--num-nodes & -M/--num-tasks-per-node"
        )
    if args.num_tasks and args.queue != "local" and HAVE_QSUB:
        sys.exit("-n option is not supported on OpenPBS")

    ensure_local_on_hpc(args)

    version = default_version(os.path.basename(sys.argv[0]))
    if args.version:
        version = args.version

    rootdir = (get_versions_path() / version).resolve()
    if not rootdir.exists():
        sys.exit(
            f"Cirrus version '{version}' is not installed in {get_versions_path()}"
        )

    progname = "cirrus"
    if args.version and args.version.split(".") < ["1", "9"]:
        progname = "pflotran"

    num_tasks = None
    if args.num_tasks:
        num_tasks = args.num_tasks
    elif args.num_nodes:
        num_tasks = args.num_nodes * args.num_tasks_per_node

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
