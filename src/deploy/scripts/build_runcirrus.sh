#!/usr/bin/env bash
set -ex

: "${out:?}"

python3.11 -m venv $out

install -m 755 -D $(dirname $0)/runcirrus.py $out/bin/runcirrus
install -D $(dirname $0)/_cirrus_logger.py $out/bin/_cirrus_logger.py

sed -i "s:/usr/bin/python3.11:${out}/bin/python:g" $out/bin/runcirrus
