use std::io::{stdout, Stdout, Write};
use std::process::exit;

use clap::Parser;

#[derive(Debug, Parser)]
#[command(about = include_str!("about.txt"), long_about = None)]
struct Args {
    #[arg(help = "Cirrus input file")]
    input: String,

    #[arg(short, long, default_value = "local")]
    queue: String,

    #[arg(short = 'N', long, default_value_t = 0)]
    num_tasks: u32,

    #[arg(short = 'n', long, default_value_t = 0)]
    num_nodes: u32,

    #[arg(short = 'm', long, default_value_t = 0)]
    num_tasks_per_node: u32,

    #[arg(short, long, default_value = "stable")]
    version: String,

    #[arg(long, help = "Print job script and exit")]
    print_job_script: bool,

    #[arg(long, value_parser = parse_print_versions)]
    print_versions: bool,
}

fn print_versions(mut io: &Stdout) {
    let _ = writeln!(io, "Current stuff:");
}

fn parse_print_versions(value: &str) -> Result<bool, String> {
    if value == "true" {
        print_versions(&stdout());
        exit(0)
    }
    Ok(false)
}

fn main() {
    let args = Args::parse();

    println!("{:?}", args);
}
