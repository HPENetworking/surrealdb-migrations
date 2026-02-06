#!/usr/bin/env bash

set -o errexit  # Error on any command error
set -o nounset  # Fail if variable unbound

# Script that generates all the necessary files and changes for the Dockerfile
# and builds it.

echo "Building mysql-migrations image"
cd "$(dirname "${BASH_SOURCE[0]}")"
docker build \
    --build-arg http_proxy \
    --build-arg https_proxy \
    --build-arg no_proxy \
    $@ -f ./Dockerfile .
