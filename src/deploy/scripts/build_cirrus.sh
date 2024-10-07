#!/usr/bin/env bash
set -ex

: "${out:?}"
: "${tmp:?}"
: "${petsc:?}"
: "${src:?}"

if ! [[ -f "$tmp/six-*-.whl" ]]
then
    python3 -m pip download -d "$tmp" six
fi

# --------------------------------------
# Build Cirrus
# --------------------------------------
cd "$src/src/cirrus"
git reset --hard
git clean -xdf

export PETSC_DIR="$petsc"
export PETSC_ARCH=
export PYTHONPATH="$tmp/six-*-.whl"

make cirrus
make test
install -D cirrus "$out/bin/cirrus"
