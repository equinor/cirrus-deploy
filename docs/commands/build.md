# karsk-build

## NAME
karsk\-build - Build a Karsk configuration locally

## SYNOPSIS
**karsk build** *config*

## DESCRIPTION
**karsk build** fetches and builds every package in the **config** file and places the result in the staging area.

Karsk uses an [OCI](https://opencontainers.org/) engine like [Podman](https://podman.io) or [Docker](https://docker.io) to build each package specified in the configuration in a sandbox, ensuring that the final binaries are built in a way that is compatible with a target system.

The **config** file contains a **build-image** field, which is a relative path to a OCI-compatible Containerfile. This describes the build environment that all packages will use. Any system-level build dependencies and runtime assumptions should be present in this file.

## OPTIONS

#### **--engine** *engine-name*

Which OCI Engine to use. *engine-name* can either be *podman* or *docker*. On Linux, the default is *podman*, while everywhere else it is *docker*.

#### **--staging**, **-s**

!!! warning
    This section describes a planned feature. Actual behaviour in Karsk may differ.

Directory in which staging files should be located.
