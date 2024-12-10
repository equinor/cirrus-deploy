Cirrus deployment scripts
=========================

These are the scripts for deploying OpenGoSim's Cirrus on-prem in Equinor. Our
copy of the source is located at https://github.com/equinor/cirrus

## Deploying

Cirrus depends on [PETSC](https://github.com/petsc/petsc) as well as other
packages that PETSC provides.

The `config` file is a file that is sourced in other bash scripts, and so must
follow bash syntax. It describes which sources to install where.

The install procedure is done through the following commands:
1. Create a python virtual environment (e.g. `python -m venv /path/to/venv`) and source it (`source /path/to/venv/bin/activate`)
2. Run `pip install .` in root folder. The cli tool `deploy` has been installed (`deploy --help` for information)
3. Run `deploy build` in order to start the build process.

