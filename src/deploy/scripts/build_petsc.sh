#!/usr/bin/env bash
set -ex

: "${out:?}"

export PETSC_DIR=$PWD
export PETSC_ARCH=gnu-c-opt

./configure                                  \
    --COPTFLAGS="$CFLAGS"                    \
    --CXXOPTFLAGS="$CXXFLAGS"                \
    --FOPTFLAGS="$FFLAGS"                    \
    --download-fblaslapack=yes               \
    --download-hdf5=yes                      \
    --download-hypre=yes                     \
    --download-mpich=yes                     \
    --download-ptscotch=yes                  \
    --download-hdf5-fortran-bindings=yes     \
    --with-debugging=0                       \
    --prefix="$out"

make all
make check
make install
