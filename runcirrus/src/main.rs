use std::ffi::OsString;
use std::fs::File;
use std::io::Write;
use std::path::{absolute, Path, PathBuf};
use std::process::{exit, Command};

use clap::Parser;
use which::which_global;

fn preparse_args() -> Vec<OsString> {
    let mut args = Vec::new();

    for arg in std::env::args_os() {
        if arg == "-nn" {
            eprintln!("Warning: '-nn' argument has been deprecated in favour of '-N'");
            args.push("-N".into());
        } else if arg == "-nm" {
            eprintln!("Warning: '-nm' argument has been deprecated in favour of '-M'");
            args.push("-M".into());
        } else if arg == "--cirrus-help" {
            args.push(arg);
            args.push("dev/null".into()); // Add dummy input
        } else {
            args.push(arg);
        }
    }

    args
}

fn has_bsub() -> bool {
    return which_global("bsub").is_ok();
}

#[derive(Parser, Debug)]
#[command(version, about = include_str!("help.txt"))]
struct Args {
    #[arg(help = "Cirrus .in file")]
    input: PathBuf,

    #[arg(
        short = 'v',
        long,
        default_value = "latest",
        env = "CIRRUS_VERSION",
        help = "Version of Cirrus to use"
    )]
    cirrus_version: String,

    #[arg(
        short,
        long,
        default_value = "local",
        help = "HPC Queue to use, or 'local' to run on this machine"
    )]
    queue: String,

    #[arg(short = 'n', long, default_value_t = 0)]
    num_tasks: i32,

    #[arg(short = 'N', long, default_value_t = 0)]
    num_nodes: i32,

    #[arg(short = 'M', long, default_value_t = 0)]
    num_tasks_per_node: i32,

    #[arg(short, long)]
    output_directory: Option<PathBuf>,

    #[arg(long, help = "Arguments to forward to 'cirrus'")]
    cirrus_args: Option<String>,

    #[arg(long, help = "Arguments to forward to 'mpirun'")]
    mpi_args: Option<String>,

    #[arg(long, help = "Arguments to forward to 'bsub', if applicable")]
    bsub_args: Option<String>,

    #[arg(long, help = "Arguments to forward to 'qsub', if applicable")]
    qsub_args: Option<String>,

    #[arg(long, default_value_t = false, help = "Output 'cirrus -help' and exit")]
    cirrus_help: bool,

    #[arg(long, default_value_t = false, help = "Output job script and exit")]
    print_job_script: bool,

    #[arg(long, help = "Telemetry script for Cirrus")]
    telemetry: Option<String>,

    #[arg(
        long,
        default_value = "/prog/pflotran/versions",
        env = "CIRRUS_VERSIONS_PATH",
        hide = true
    )]
    cirrus_versions_path: PathBuf,
}

impl Args {
    fn num_total_tasks(&self) -> u16 {
        if self.num_tasks > 0 {
            self.num_tasks
        } else if self.num_nodes > 0 {
            self.num_nodes * self.num_tasks_per_node
        } else {
            0
        }
    }

    fn output_with_ext(&self, extension: &str) -> PathBuf {
        let mut path = self.output_directory.clone().unwrap_or_else(|| self.input.clone());
        path.set_extension(extension);
        return path
    }
}

fn validate_args(args: &mut Args) {
    if args.num_nodes > 0 && args.num_tasks_per_node <= 0 {
        eprintln!("When specifying -N/--num-nodes, you must also specify -M/--num-tasks-per-node");
    } else if args.num_nodes > 0 && args.num_tasks_per_node <= 0 {
        eprintln!("When specifying -M/--num-tasks-per-node, you must also specify -N/--num-nodes");
    } else if args.num_nodes > 0 && args.num_tasks > 0 {
        eprintln!("Specify exactly one of -n/--num-tasks or -N/--num-nodes");
    } else if ["LSD_DJOB_RANKFILE", "PBS_NODEFILE"].iter().any(|x| std::env::var_os(x).is_some()) {
        args.queue = "local".into();
        if args.num_tasks == 0 {
            args.num_tasks = 1;
        }

        return;
    } else {
        return;
    }

    exit(1);
}

fn get_version_root(args: &Args) -> PathBuf {
    std::fs::canonicalize(args.cirrus_versions_path.join(&args.cirrus_version)).unwrap_or_else(
        |err| {
            eprintln!(
                "Could not locate Cirrus version '{}': {}",
                args.cirrus_version, err
            );
            exit(1);
        },
    )
}

fn get_program_name(root: &Path) -> &'static str {
    let file_name = root.file_name().unwrap().to_str().unwrap();
    if let Ok(v) = semver::Version::parse(file_name) {
        if v.major == 1 && v.minor <= 8 {
            return "pflotran";
        }
    }
    "cirrus"
}

fn run_local(args: &Args, script: &str) -> ! {
    eprintln!("/usr/bin/bash -c <SCRIPT>");

    let status = Command::new("/usr/bin/bash")
        .arg("-c")
        .arg(script)
        .status()
        .unwrap();
    exit(status.code().unwrap_or(1));
}

fn run_bsub(args: &Args, script: &str) {
    let mut resources: Vec<String> = vec!["select[rhel >= 8]".into(), "same[type:model]".into()];
    if args.num_tasks_per_node > 0 {
        resources.push(format!("span[ptile={}]", args.num_tasks_per_node));
    }
    let resource_string = resources.join(" ");

    let user_args = args.qsub_args.clone().unwrap_or_default();

    let script_path = args.output_with_ext("run");
    let mut script_file = File::create(&script_path).unwrap();
    script_file.write_all(script.as_bytes()).unwrap();

    let status = Command::new("bsub")
        .arg("-q")
        .arg(args.queue.clone())
        .arg("-n")
        .arg(args.num_total_tasks().to_string())
        .arg("-o")
        .arg(args.output_with_ext("bsub.LOG"))
        .arg("-J")
        .arg(format!("Cirrus_{}", args.input.file_name().unwrap().to_str().unwrap()))
        .arg("-R")
        .arg(resource_string)
        .arg("--")
        .arg("/usr/bin/bash")
        .arg(script_path)
        .status()
        .unwrap();

    exit(status.code().unwrap_or(1));
}

fn main() {
    let mut args = Args::parse_from(preparse_args());
    validate_args(&mut args);
    let args = args;

    let root = get_version_root(&args);
    let progname = get_program_name(&root);

    if args.cirrus_help {
        let status = Command::new(root.join("bin").join(progname))
            .arg("-help")
            .status()
            .unwrap();
        exit(status.code().unwrap_or(1));
    }

    let input = absolute(&args.input).unwrap_or_else(|err| panic!("Could not absolute: {}", err));
    if !input.is_file() {
        eprintln!(
            "Input '{}' does not exist or isn't a regular file",
            input.display()
        );
        exit(1);
    }

    let workdir = absolute(
        args.output_directory.clone()
            .unwrap_or_else(|| input.parent().unwrap().to_path_buf()),
    )
    .unwrap();
    let case = input
        .file_stem()
        .and_then(|x| x.to_str())
        .unwrap_or("cirrus");
    let num_tasks = if args.num_tasks > 0 {
        Some(args.num_tasks)
    } else if args.num_nodes > 0 {
        Some(args.num_nodes * args.num_tasks)
    } else {
        None
    };

    let num_tasks_arg = num_tasks.map(|n| format!("-np {}", n)).unwrap_or_default();

    let script = format!(
        include_str!("job.sh.in"),
        root = root.display(),
        workdir = workdir.display(),
        input_file = input.display(),
        case = case,
        progname = progname,
        mpi_args = args.mpi_args.clone().unwrap_or_default(),
        cirrus_args = args.cirrus_args.clone().unwrap_or_default(),
        num_tasks = num_tasks_arg,
        telemetry = args.telemetry.clone().unwrap_or_default(),
    );

    if args.print_job_script {
        println!("{}", script);
        exit(1);
    }

    if args.queue == "local" {
        run_local(&args, &script);
    } else if has_bsub() {
        run_bsub(&args, &script);
    } else {
        eprintln!("No supported job scheduler detected on this machine");
        exit(1);
    }
}
