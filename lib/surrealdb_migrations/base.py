# Copyright (C) 2024-2026 Hewlett Packard Enterprise Development LP.
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
Module for migrations base class.
"""


class BaseMigration:
    """
    Base class for all migrations.

    The user will subclass this class and implement the upgrade and downgrade
    methods.

    The upgrade method will be called when the migration is applied, and the
    downgrade method will be called when the migration is rolled back.

    :param Namespace config: runtime configuration to execute migration.
    """

    def __init__(self, config):
        self.config = config

    async def upgrade(self, db):
        """
        Apply the migration.

        :param db: The database connection.
        """
        raise NotImplementedError

    async def downgrade(self, db):
        """
        Rollback the migration.

        :param db: The database connection.
        """
        raise NotImplementedError


__all__ = [
    'BaseMigration',
]
