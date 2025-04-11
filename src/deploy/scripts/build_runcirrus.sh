#!/usr/bin/env bash
set -ex

: "${out:?}"

python3.11 -m venv $out
$out/bin/pip install $src
