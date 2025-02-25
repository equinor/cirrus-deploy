#!/usr/bin/env bash

mkdir $out/bin
cc -o $out/bin/bar $src/bar.c -L$foo/lib -lfoo -Wl,-rpath,$foo/lib
