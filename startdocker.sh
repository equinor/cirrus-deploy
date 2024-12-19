#!/bin/bash
export DOCKER_BUILDKIT=1

IMAGE_NAME=cirrus_deploy
AUTH_SOCK_DIR=$(dirname $SSH_AUTH_SOCK)
docker build -t $IMAGE_NAME .
docker run --rm -it -v $PWD:$PWD -w $PWD -v $PWD/docker_folder:/prog/cirrus \
  \
  $IMAGE_NAME # -v $AUTH_SOCK_DIR:$AUTH_SOCK_DIR -e SSH_AUTH_SOCK=$SSH_AUTH_SOCK \
