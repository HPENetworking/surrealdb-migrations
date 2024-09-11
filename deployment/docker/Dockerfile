# -*- coding: utf-8 -*-
#
# Copyright (C) 2024 Hewlett Packard Enterprise Development LP.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
# License for the specific language governing permissions and limitations under
# the License.


#######################
# BASE CONTAINER      #
#######################

FROM ubuntu:20.04 as base
ENV DEBIAN_FRONTEND noninteractive


# Setup and install base system Software
RUN echo "locales locales/locales_to_be_generated multiselect en_US.UTF-8 UTF-8" | debconf-set-selections \
    && echo "locales locales/default_environment_locale select en_US.UTF-8" | debconf-set-selections \
    && apt-get update \
    && apt-get --yes --no-install-recommends install \
        # Base Software
        locales tzdata ca-certificates \
        # Developer Software
        bash-completion nano tree \
        # Networking Software
        curl iproute2 iputils-ping \
    && rm -rf /var/lib/apt/lists/*
ENV LANG en_US.UTF-8


# Install HPE CA
RUN curl --insecure \
        https://pvsdk-archive.rose.rdlabs.hpecorp.net/HPE_PrivateRootCA.crt \
        -o /usr/local/share/ca-certificates/HPE_PrivateRootCA.crt \
    && update-ca-certificates


# Install Python runtime stack
RUN apt-get update \
    && apt-get --yes --no-install-recommends install \
        python3 python3-setuptools \
    && rm -rf /var/lib/apt/lists/*


#######################
# BUILD CONTAINER     #
#######################

FROM base as builder


# Install Python development stack
RUN apt-get update \
    && apt-get --yes --no-install-recommends install \
        python3-dev python3-pip python3-wheel \
        build-essential cmake git \
    && rm -rf /var/lib/apt/lists/*


# Configure pip to use HPE PyPI
RUN mkdir -p /root/.config/pip/ \
    && echo "\
[global]\n\
index-url = https://pvsdk-pypi.rose.rdlabs.hpecorp.net/\n\
" > /root/.config/pip/pip.conf \
    && cat /root/.config/pip/pip.conf


# NOTE: Uncomment and edit if needed
# Install native development dependencies
# RUN apt-get update \
#     && apt-get --yes --no-install-recommends install \
#         a-native-depedency \
#     && rm -rf /var/lib/apt/lists/*


# Install package
COPY . /src
WORKDIR /src
RUN tree . \
    && pip3 install --no-warn-script-location --prefix=/build .


######################
# RUN CONTAINER      #
######################

FROM base as runner
WORKDIR /root


# NOTE: Uncomment and edit if needed
# Install native runtime dependencies
# RUN apt-get update \
#     && apt-get --yes --no-install-recommends install \
#         a-native-depedency \
#     && rm -rf /var/lib/apt/lists/*


# Copy build tree
COPY --from=builder /build /usr/local
ENV PYTHONPATH /usr/local/lib/python3.8/site-packages


# Run package entrypoint
CMD python3 -m surrealdb-migrations
