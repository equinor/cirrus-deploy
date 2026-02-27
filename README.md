Cirrus deployment scripts
=========================

These are the scripts for deploying OpenGoSim's Cirrus on-prem in Equinor.

## Deploying

Cirrus depends on [PETSC](https://github.com/petsc/petsc) as well as other
packages that PETSC provides.

The `config` file is a file that is sourced in other bash scripts, and so must
follow bash syntax. It describes which sources to install where.

The install procedure is done through the following commands:
1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/): the package manager that we use
2. Run `uv sync` in root folder. The cli tool `deploy` has been installed (`deploy --help` for information)
3. Run `deploy build` in order to start the build process.

# Development Using Docker

```bash
git clone git@github.com:equinor/cirrus-deploy.git
cd cirrus-deploy
```

The Dockerfile contains the required build tools in order to compile and run cirrus/pflotran.

```bash
docker build . -t cirrus
```

Run the docker image interactively. Consider including volume mounts to get test_data etc, and work on the files

```bash
docker run --rm -v $PWD:/work -v $PWD/_output:/root/cirrus -it cirrus
```

Now inside the docker image run the commands to build and install

```bash
deploy build
deploy test
deploy links
```

Set the path variable to the system path:

```bash
export CIRRUS_VERSIONS_PATH=/root/cirrus/versions
```

You should now have `runcirrus` in your path inside the docker container
