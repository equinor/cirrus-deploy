#!/usr/bin/env bash
set -ex

: "${out:?}"

install -m 755 -D $(dirname $0)/runcirrus.py $out/bin/runcirrus
