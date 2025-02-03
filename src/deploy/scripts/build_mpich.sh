#!/usr/bin/env bash
set -ex

: "${out:?}"

./configure                      \
    --disable-java               \
    --without-hwloc              \
    --with-device=ch4:ucx        \
    --enable-g=meminit           \
    --disable-maintainer-mode    \
    --disable-dependency-tracker \
    --prefix="$out"

make all
make check
make install
