#!/bin/bash
export DOCKER_BUILDKIT=1

IMAGE_NAME=cirrus_deploy
docker build -t $IMAGE_NAME .
docker run --rm -it --ssh -v $PWD:$PWD -w $PWD -v docker_folder:/prog/cirrus \
  -v $(dirname $SSH_AUTH_SOCK) -e SSH_AUTH_SOCK=$SSH_AUTH_SOCK \
  $IMAGE_NAME
