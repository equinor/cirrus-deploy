Cirrus deployment scripts
=========================

These are the scripts for deploying OpenGoSim's Cirrus on-prem in Equinor. Our
copy of the source is located at https://github.com/equinor/cirrus

## Deploying

Cirrus depends on [PETSC](https://github.com/petsc/petsc) as well as other
packages that PETSC provides.

The `config` file is a file that is sourced in other bash scripts, and so must
follow bash syntax. It describes which sources to install where.

The other files will build and deploy the environment, and must be run in the
following order:
1. `build_petsc`: Builds PETSC and installs it to
   `/prog/pflotran/deployments/.builds`
2. `build_cirrus`: Builds Cirrus and installs it to
   `/prog/pflotran/deployments/.builds`, using the PETSC version in `config` file
3. `build_env`: Builds the target environment containing our wrapper scripts
   (located in this repo) and installs it to `/prog/pflotran/deployments`, using
   the Cirrus and PETSC versions in the `config` file
4. `deploy`: Rsync the newly created environments to multiple locations, and
   create symlinks.
   
Steps can be skipped if the previous steps are unchanged. For example, if
updating Cirrus, only `config` needs to be changed, and step 2 and onwards needs
to be ran. Ie, `build_petsc` can often be skipped.
