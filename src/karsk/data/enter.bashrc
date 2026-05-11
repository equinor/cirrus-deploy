#!/usr/bin/env bash

if [ -f /etc/bashrc ]; then
  . /etc/bashrc
fi

if [ -n "${KARSK_PATH:-}" ]; then
  export PATH="${KARSK_PATH}:$PATH"
fi

if [ -n "${PS1:-}" ]; then
  PS1="(Karsk 🥃) ${PS1}"
fi
