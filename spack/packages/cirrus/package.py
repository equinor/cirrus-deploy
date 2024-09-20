# Copyright 2013-2024 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

# ----------------------------------------------------------------------------
# If you submit this package back to Spack as a pull request,
# please first remove this boilerplate and all FIXME comments.
#
# This is a template package file for Spack.  We've put "FIXME"
# next to all the things you'll want to change. Once you've handled
# them, you can save this file and test your package like this:
#
#     spack install cirrus
#
# You can edit this file again by typing:
#
#     spack edit cirrus
#
# See the Spack documentation for more information on packaging.
# ----------------------------------------------------------------------------

from spack.package import *


class Cirrus(Package):
    """FIXME: Put a proper description of your package here."""

    # FIXME: Add a proper url for your package's homepage here.
    homepage = "https://www.example.com"
    git = "git@github.com:equinor/cirrus.git"

    # FIXME: Add a list of GitHub accounts to
    # notify when the package is updated.
    # maintainers("github_user1", "github_user2")

    # FIXME: Add the SPDX identifier of the project's license below.
    # See https://spdx.org/licenses/ for a list. Upon manually verifying
    # the license, set checked_by to your Github username.
    license("UNKNOWN", checked_by="pinkwah")

    version("1.9.1", commit="429bc6f9104e66bb7eebcb154d1e32f277bc1146")

    depends_on("py-six", type=("build"))
    depends_on("hdf5+fortran+hl")
    depends_on("petsc@3.19.1+hdf5+hypre+mpi+fortran+ptscotch~metis~superlu-dist")

    def install(self, spec, prefix):
        cd("src/cirrus")
        make("cirrus")
        # make("test")
        mkdirp(join_path(prefix, "bin"))
        install("cirrus", join_path(prefix, "bin/cirrus"))
