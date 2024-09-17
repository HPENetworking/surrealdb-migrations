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
from pathlib import Path
from logging import getLogger
from datetime import datetime, timezone
from importlib import util

from surrealdb import Surreal


log = getLogger(__name__)


MIGRATION_TPL = """\
from surrealdb_migrations.base import BaseMigration


class Migration(BaseMigration):

    def upgrade(self):
        pass

    def downgrade(self):
        pass
"""


class MigrationsManager:
    """
    FIXME: Document.

    :param Namespace config: runtime configuration to manage migrations.
    """

    def __init__(self, config):
        self.config = config
        self.db = None

    def _connect(self):

        password_env = self.config.database.password_env
        password = environ.get(password_env, None)
        if password is None:
            raise RuntimeError(
                'Database password environment variable '
                f'{password_env} is not set'
            )

        log.info(f'Connecting SurrealDB at {self.config.database.url} ...')
        self.db = Surreal(self.config.database.url)
        self.db.signin({
            'username': self.config.database.username,
            'password': password,
        })
        log.info('Successfully connected and signed in!')

    def do_create(self, name):
        """
        Create a new migration file.
        """
        directory = Path(self.config.migrations.directory)
        directory.mkdir(parents=True, exist_ok=True)

        now = datetime.now(tz=timezone.utc)

        filename = directory / '{}_{}.py'.format(
            now.isoformat(),
            name.lower().replace(' ', '_').replace('-', '_'),

        )
        log.info(f'Creating migration file {filename} ...')

        filename.write_text(MIGRATION_TPL, encoding='utf-8')
        log.info(f'Migration file {filename} created!')

    def _list_db_migrations(self):
        # migrations = self.db.query(
        #     f'SELECT name FROM {self.config.migrations.metastore} '
        #     'ORDER BY created_at DESC'
        # )
        # migrations[0].get('result', [])
        return []

    def _list_migrations(self):
        directory = Path(self.config.migrations.directory)
        return sorted(directory.glob('*.py'))

    def _insert_migration(self, migration):
        """
        Store the migration's timestamp in the database.
        """
        query = (
            f'CREATE {self.config.migrations.metastore} SET '
            'name = $name, '
            'created_at =  $timestamp; '
        )
        migration = self.db.query(
            query,
            {'name': migration, 'timestamp': datetime.now(tz=timezone.utc)}
        )

        return next(iter(migration))

    def do_migrate(self, to_datetime=None):
        """
        Execute all relevant migrations.
        """
        directory = Path(self.config.migrations.directory)
        log.info(f'Executing migration up to {to_datetime.isoformat()} ...')

        files = self._list_migrations()
        self._connect()
        applied_migrations = self._list_db_migrations()

        migrations_to_apply = [
            migration_file.name for migration_file in files
            if (
                not applied_migrations or
                migration_file > applied_migrations[0]
            )
        ]

        if to_datetime:
            migrations_to_apply = list(
                filter(
                    lambda migration: migration < to_datetime.isoformat(),
                    migrations_to_apply
                )
            )

        for migration in migrations_to_apply:
            try:
                spec = util.spec_from_file_location(migration, directory / migration)  # noqa
                module = util.module_from_spec(spec)
                spec.loader.exec_module(module)
                migration_obj = module.Migration(config=self.config)
                migration_obj.db = self.db
                migration_obj.upgrade()
                self._insert_migration(migration)
            except Exception as e:
                log.error(f'Failed to apply: {migration}')
                if hasattr(e, 'message'):
                    log.error(e.message)
                raise e

    def _delete_migration(self, migration):
        # self.db.delete(f'{self.config.migrations.metastore}:migration')
        query = (
            f'DELETE {self.config.migrations.metastore} WHERE name = $name; '
        )
        self.db.query(query, {'name': migration})

    def do_rollback(self, to_datetime=None):
        """
        Rollback all relevant migrations.
        """
        log.info(f'Executing rollback down to {to_datetime.isoformat()} ...')
        self._connect()

    def do_list(self):
        log.info(self._list_migrations())


__all__ = [
    'MigrationsManager',
]
