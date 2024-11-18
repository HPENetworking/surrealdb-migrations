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
Module to manage (create, migrate, rollback and list) migrations.
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

    async def upgrade(self, db):
        pass

    async def downgrade(self, db):
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

    async def _connect(self):

        password_env = self.config.database.password_env
        password = environ.get(password_env, None)
        if password is None:
            raise RuntimeError(
                'Database password environment variable '
                f'{password_env} is not set'
            )

        log.info(f'Connecting SurrealDB at {self.config.database.url} ...')

        self.db = Surreal(self.config.database.url)
        await self.db.connect()
        await self.db.signin({
            'user': self.config.database.username,
            'pass': password,
        })
        await self.db.use(
            self.config.database.namespace,
            self.config.database.database,
        )

        log.info('Successfully connected and signed in!')

    async def _close(self):
        log.debug('Closing database connection ...')
        await self.db.close()
        log.debug('Database connection successfully closed!')

    async def __aenter__(self):
        await self._connect()
        return

    async def __aexit__(self, type, value, traceback):
        await self._close()

    def do_create(self, name):
        """
        Create a new migration file.
        """
        directory = Path(self.config.migrations.directory)
        directory.mkdir(parents=True, exist_ok=True)

        # ISO8601 is not file system safe, doing base replacement to keep
        # some amount of compatibility
        now = datetime.now(tz=timezone.utc).isoformat()
        for replace, replacement in (
            ('.', '_'),
            (':', '_'),
            ('+', '_'),
        ):
            now = now.replace(replace, replacement)

        filename = directory / '{}_{}.py'.format(
            now,
            # TODO: Improve, create a slug function
            name.lower().replace(' ', '_').replace('-', '_'),
        )
        log.info(f'Creating migration file {filename} ...')

        filename.write_text(MIGRATION_TPL, encoding='utf-8')
        log.info(f'Migration file {filename} created!')

    def _list_fs_migrations(self):
        directory = Path(self.config.migrations.directory)
        migrations = sorted(directory.glob('*.py'))

        log.info(f'Migrations located at {directory}:')
        for migration in migrations:
            log.info(f'-> {migration.name}')

        return migrations

    def do_list(self):
        self._list_fs_migrations()

    async def _list_db_migrations(self):
        migrations = await self.db.query(
            'SELECT name, applied_date '
            f'FROM {self.config.migrations.metastore} '
            'ORDER BY applied_date DESC'
        )
        result = migrations[0].get('result', []) if migrations else []

        return [item['name'] for item in result]

    async def do_status(self):
        applied = await self._list_db_migrations()

        if not applied:
            log.info('No migrations are applied in the database')
            return

        log.info('Current applied migrations in the database:')
        for migration in applied:
            log.info(f'-> {migration}')

    async def _create_metastore_table(self):
        table = self.config.migrations.metastore
        query = (
            f'DEFINE TABLE IF NOT EXISTS {table} SCHEMAFULL; '
            f'DEFINE FIELD IF NOT EXISTS id ON {table}; '
            f'DEFINE FIELD IF NOT EXISTS name ON {table} TYPE string; '
            'DEFINE FIELD IF NOT EXISTS applied_date '
            f'ON {table} TYPE datetime;'
        )
        await self.db.query(query)
        log.debug('Successfully created the metastore table!')

    async def _insert_migration(self, migration):
        """
        Store the migration's timestamp in the database.
        """
        query = (
            f'CREATE {self.config.migrations.metastore} SET '
            'name = $name, '
            'applied_date = $time '
        )
        migration = await self.db.query(
            query,
            {
                'name': migration,
                'time': f'd"{datetime.now(tz=timezone.utc).isoformat()}"',
            }
        )
        return next(iter(migration))

    def _import_module(self, migration):
        """
        Dynamically loads a file as a Python module and executes it.

        :param migration (str): The name of the migration file to load.

        :return module: The dynamically loaded Python module.
        """
        directory = Path(self.config.migrations.directory)

        spec = util.spec_from_file_location(
            migration, directory / migration,
        )
        module = util.module_from_spec(spec)
        spec.loader.exec_module(module)

        return module

    async def do_migrate(self, to_datetime=None):
        """
        Execute all relevant migrations.
        """
        log.info(f'Executing migration up to {to_datetime.isoformat()} ...')

        files = self._list_fs_migrations()

        log.info('Fetching applied migrations ...')
        migrations_applied = await self._list_db_migrations()

        if not migrations_applied:
            log.info('No migrations are applied')
        else:
            log.info(
                f'Migrations applied: {len(migrations_applied)}'
            )
            for applied in migrations_applied:
                log.info(f'-> {applied}')

        migrations_to_apply = [
            migration_file.name for migration_file in files
            if (
                not migrations_applied
                or migration_file.name > migrations_applied[0]
            )
        ]

        if to_datetime:
            migrations_to_apply = list(
                filter(
                    lambda migration: migration < to_datetime.isoformat(),
                    migrations_to_apply
                )
            )

        if not migrations_to_apply:
            log.info('No migrations need to be applied')
            return

        await self._create_metastore_table()
        log.info(f'Applying {len(migrations_to_apply)} migrations ...')

        for migration in migrations_to_apply:
            try:
                log.info(f'-> {migration}')

                module = self._import_module(migration)
                # Execute migration
                migration_obj = module.Migration(self.config)
                await migration_obj.upgrade(self.db)

                await self._insert_migration(migration)

            except Exception as e:
                log.error(f'Failed to apply: {migration}')
                if hasattr(e, 'message'):
                    log.error(e.message)

                raise e

        log.info(
            f'Successfully applied {len(migrations_to_apply)} migrations'
        )

    async def _delete_migration(self, migration):
        # self.db.delete(f'{self.config.migrations.metastore}:migration')
        query = (
            f'DELETE {self.config.migrations.metastore} WHERE name = $name; '
        )
        await self.db.query(query, {'name': migration})

    async def do_rollback(self, to_datetime=None):
        """
        Rollback all relevant migrations.
        """
        log.info(f'Executing rollback down to {to_datetime.isoformat()} ...')


__all__ = [
    'MigrationsManager',
]
