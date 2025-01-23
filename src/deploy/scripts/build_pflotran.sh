#!/usr/bin/env bash
set -ex

: "${out:?}"
: "${tmp:?}"
: "${petsc:?}"
: "${src:?}"

# --------------------------------------
# Build Pflotran-OGS
# --------------------------------------
cd "$src/src/pflotran"
git reset --hard
git clean -xdf

export PETSC_DIR="$petsc"
export PETSC_ARCH=

make UPDATE_PROVENANCE=0 pflotran
make UPDATE_PROVENANCE=0 check
install -D pflotran "$out/bin/pflotran"
