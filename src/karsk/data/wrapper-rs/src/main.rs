mod util;
mod versions;

use std::env::{args_os, current_exe};
use std::ffi::OsString;
use std::io::stdout;
use std::os::unix::process::CommandExt;
use std::path::PathBuf;
use std::process::Command;

use crate::util::exit;
use crate::versions::print_versions_to;

const DEFAULT_VERSION: &str = "stable";

fn main() {
    let mut args = args_os();

    let executable = current_exe().expect("Couldn't obtain the wrapper's executable path");
    let exename = args
        .next()
        .map(PathBuf::from)
        .and_then(|arg0| arg0.file_name().map(|s| s.to_owned()))
        .expect("Couldn't obtain the wrapper's executable name");

    let versions_dir = executable
        .parent()
        .and_then(|p| p.parent())
        .map(|p| p.join("versions"))
        .expect("Couldn't determine 'versions' directory");

    let mut help_arg: Option<OsString> = None;
    let mut version = OsString::from(DEFAULT_VERSION);

    let mut reinsert_arg1: Option<OsString> = None;
    if let Some(arg1) = args.next() {
        if arg1 == "-h" || arg1 == "--help" {
            help_arg = Some(arg1);
        } else if arg1 == "--print-versions" {
            print_versions_to(versions_dir, &mut stdout());
            return;
        } else if (arg1 == "-v" || arg1 == "--version")
            && let Some(arg2) = args.next()
        {
            version = arg2;
        } else {
            reinsert_arg1 = Some(arg1);
        }
    }

    if !versions_dir.join(&version).exists() {
        exit!("No such version: {:?}", version);
    }

    let program = versions_dir.join(version).join("bin").join(exename);
    let mut command = Command::new(program);
    if let Some(arg1) = help_arg {
        usage();
        command.arg(arg1);
    } else {
        if let Some(arg1) = reinsert_arg1 {
            command.arg(arg1);
        }
        command.args(args);
    }

    let err = command.exec();
    exit!("Couldn't start program: {}", err);
}

fn usage() {
    let project_name = current_exe()
        .ok()
        .and_then(|p| p.parent().map(|p| p.to_owned())) // "[program]/bin/"
        .and_then(|p| p.parent().map(|p| p.to_owned())) // "[program]/"
        .and_then(|p| p.file_name().map(|s| s.to_owned()))
        .unwrap_or_else(|| OsString::from("the program"));

    println!(
        "Wrapper usage: {} [ARGS...]",
        args_os()
            .next()
            .map(|x| x.display().to_string())
            .unwrap_or_else(|| String::from(".wrapper"))
    );
    println!();
    println!("This program is built with Karsk which uses a version-aware wrapper.");
    println!(
        "Use the following arguments to modify which version of {:?} to run.",
        project_name
    );
    println!("See Karsk documentation for more information: https://equinor.github.io/karsk");
    println!();
    println!("    --help, -h            - Print this help message");
    println!("    --version, -v [NAME]  - Use a different version");
    println!("    --print-versions      - List available versions");
    println!();
}
