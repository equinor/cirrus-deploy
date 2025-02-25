#!/usr/bin/env bash

mkdir $out/lib
cc -shared -fPIC -o $out/lib/libfoo.so $src/foo.c
