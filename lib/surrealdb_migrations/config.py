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

"""
Configuration loading module.
"""

from pathlib import Path
from importlib.resources import files

from tomli import loads
from objns import Namespace


def load_config(configfile):
    """
    Read the given TOML configuration file.

    :param Path configfile: Path to a TOML configuration file.

    :return: The parsed configuration file as an objns Namespace.
    :rtype: Namespace
    """
    config = Namespace(loads(
        files(__package__).joinpath(
            'data/config.toml'
        ).read_text(encoding='utf-8')
    ))

    if configfile is None:
        return config

    assert isinstance(configfile, Path)
    assert configfile.is_file()

    config.update(loads(
        configfile.read_text(encoding='utf-8')
    ))
    return config


__all__ = [
    'load_config'
]
