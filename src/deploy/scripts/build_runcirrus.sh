#!/usr/bin/env bash
set -ex

: "${out:?}"
: "${src:?}"

install -m 755 -D $src $out/bin/runcirrus
