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
Module to manage (create, upgrade, downgrade) migrations.
"""

from os import environ

from surrealdb import SurrealDB


class MigrationManager:
    """
    FIXME: Document.

    :param Namespace config: runtime configuration to manage migrations.
    """

    def __init__(self, config):
        self.config = config

    def _connect(self):

        password_env = self.config.database.password_env
        password = environ.get(password_env, None)
        if password is None:
            raise RuntimeError(
                'Database password environment variable '
                f'{password_env} is not set'
            )

        self.db = SurrealDB(self.config.database.url)
        self.db.signin({
            'username': self.config.database.username,
            'password': password,
        })

    def do_create(self):
        """
        Create a new migration file.
        """

    def do_migrate(self, to_datetime=None):
        """
        Execute all relevant migrations.
        """

    def do_rollback(self, to_datetime=None):
        """
        Rollback all relevant migrations.
        """


__all__ = [
    'MigrationManager',
]
