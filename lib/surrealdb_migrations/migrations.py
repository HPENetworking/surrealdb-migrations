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
Module to manage (create, migrate, rollback and list) migrations.
"""

from os import environ
from pathlib import Path
from importlib import util
from typing import Optional
from logging import getLogger
from datetime import datetime, timezone

from tabulate import tabulate
from surrealdb import AsyncSurreal, AsyncSurrealSession, NotFoundError


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
    Manager for handling database migrations.

    This class provides methods to create, apply, rollback, and list
    migrations files and their status in the database.

    :param Namespace config: runtime configuration to manage migrations.
    """

    def __init__(self, config):
        self.config = config
        self._connection: Optional[AsyncSurreal] = None
        self.db: Optional[AsyncSurrealSession] = None

    async def _connect(self):
        """
        Connects to the SurrealDB database using the provided configuration.

        This method retrieves the database password from the environment
        variable specified in the configuration, establishes a connection to
        the database, and signs in with the provided credentials. It also
        selects the appropriate namespace and database for subsequent
        operations.

        This private method is intended is not meant to be called directly by
        external code, use the context manager interface instead.

        :raises RuntimeError: If the database password environment variable is
         unset.
        """
        log.info(
            'Connecting to SurrealDB with the following configuration:'
            f'\n{self.config}'
        )

        # Grab password from environment variable
        password_env = self.config.database.password_env
        password = environ.get(password_env, None)
        if password is None:
            raise RuntimeError(
                'Database password environment variable '
                f'{password_env} is not set'
            )

        # Connect to SurrealDB
        self._connection = AsyncSurreal(self.config.database.url)
        await self._connection.connect()

        # Create a new session, sign in and select namespace and database
        self.db = await self._connection.new_session()

        log.info(
            f'Connecting via {self.config.database.url} '
            f'as {self.config.database.username!r}'
        )
        await self.db.signin({
            'username': self.config.database.username,
            'password': password,
        })

        log.info(
            f'Using namespace {self.config.database.namespace!r} and '
            f'database {self.config.database.database!r} ...'
        )
        await self.db.use(
            namespace=self.config.database.namespace,
            database=self.config.database.database,
        )

        log.info('Successfully connected and signed in!')

    async def _close(self):
        """
        Closes the connection to the SurrealDB database if it exists.

        This private method is intended is not meant to be called directly by
        external code, use the context manager interface instead.
        """
        if self._connection is not None:

            if self.db is not None:
                log.debug('Closing database session ...')
                await self.db.close_session()
                log.debug('Database session successfully closed!')
                self.db = None

            log.debug('Closing database connection ...')
            await self._connection.close()
            log.debug('Database connection successfully closed!')
            self._connection = None

    async def __aenter__(self):
        """
        Connects to the database when entering the context.

        Example usage:

        ::

            mgr = MigrationsManager(config)
            async with mgr:
                await mgr.do_status()

        Or:

        ::

            async with MigrationsManager(config) as mgr:
                await mgr.do_status()

        :return MigrationsManager: The instance of the manager with an active
         connection.
        """
        await self._connect()
        return self

    async def __aexit__(self, type, value, traceback):
        """
        Closes the database connection when exiting the context.
        """
        await self._close()

    def do_create(self, name):
        """
        Create a new migration file.

        :param str name: The name of the migration to create.

        :return Path: The path to the created migration file.
        :rtype: pathlib.Path
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

        return filename

    def _list_fs_migrations(self):
        """
        List all migration files in the configured directory.

        :return list: A list of migration files sorted by name (older first).
         The name of the file is expected to start with an ISO8601 timestamp to
         ensure the correct order of migrations.
         If no migration files are found, an empty list is returned.
        :rtype: list[pathlib.Path]
        """
        directory = Path(self.config.migrations.directory).resolve()
        migrations = sorted(directory.glob('*.py'))

        if not migrations:
            log.info(f'No migration files found at {directory}')
        else:
            table = tabulate(
                [
                    [migration.name]
                    for migration in migrations
                ],
                headers=['Migration Files'],
                tablefmt='rounded_outline',
            )
            log.info(f'Migrations located at {directory}:\n{table}')

        return migrations

    def do_list(self):
        """
        List all migration files in the configured directory.

        :return list: A list of migration files sorted by name (older first).
        :rtype: list[pathlib.Path]
        """
        return self._list_fs_migrations()

    async def _list_db_migrations(self):
        """
        List all applied migrations in the database.

        :return list: A list of applied migrations (name and applied_date)
         sorted by applied date in descending order (newer first).

         ::

            [
                {
                    'name': '2024-01-01T00_00_00Z_initial_migration.py',
                    'applied_date': '2024-01-01T00:00:00Z',
                },
                ...
            ]

        :rtype: list[dict]
        """
        table = self.config.migrations.metastore

        log.info('Fetching applied migrations ...')
        try:
            result = await self.db.query(
                'SELECT name, applied_date '
                f'FROM {table} '
                'ORDER BY applied_date DESC;'
            )

        except NotFoundError as e:
            if e.table_name is None:
                raise e

            # Table doesn't exist yet, totally fine
            result = []

        if not result:
            log.info('No migrations are currently applied in the database')
            return result

        migrations = [
            {
                key: item[key]
                for key in ('name', 'applied_date')
            }
            for item in result
        ]

        table = tabulate(
            [
                [migration['name'], migration['applied_date']]
                for migration in migrations
            ],
            headers=['Name', 'Applied Date'],
            tablefmt='rounded_outline',
        )
        log.info(
            f'Migrations currently applied in the database:\n{table}'
        )

        return migrations

    async def do_status(self):
        """
        List all applied migrations in the database.

        :return list: A list of applied migrations (name and applied_date)
         sorted by applied date in descending order (newer first).

         ::

            [
                {
                    'name': '2024-01-01T00_00_00Z_initial_migration.py',
                    'applied_date': '2024-01-01T00:00:00Z',
                },
                ...
            ]

        :rtype: list[dict]
        """
        return await self._list_db_migrations()

    async def _create_metastore_table(self):
        """
        Create the metastore table if it does not exist.

        This table is used to store the applied migrations and their
        timestamps.
        """
        table = self.config.migrations.metastore
        query = (
            f'DEFINE TABLE IF NOT EXISTS {table} SCHEMAFULL; '
            f'DEFINE FIELD IF NOT EXISTS name '
            f'ON {table} TYPE string; '
            f'DEFINE FIELD IF NOT EXISTS applied_date '
            f'ON {table} TYPE datetime; '
            f'DEFINE INDEX IF NOT EXISTS unique_migration '
            f'ON {table} COLUMNS name UNIQUE; '
        )
        await self.db.query(query)
        log.debug('Successfully created the metastore table!')

    async def _insert_migration(self, migration):
        """
        Insert a record of the applied migration into the metastore table.

        :param str migration: The name of the migration to insert.
        """
        table = self.config.migrations.metastore
        query = (
            f'CREATE {table} SET '
            'name = $name, '
            'applied_date = <datetime>$time;'
        )

        response = await self.db.query(
            query,
            {
                'name': migration,
                'time': datetime.now(tz=timezone.utc).isoformat(),
            }
        )

        record = next(iter(response))
        log.info(
            f'Migration record inserted into metastore {table!r}:\n{record}'
        )
        return record

    def _import_module(self, migration):
        """
        Dynamically loads a file as a Python module and executes it.

        :param migration (str): The name of the migration file to load.

        :return module: The dynamically loaded Python module.
        """
        directory = Path(self.config.migrations.directory)
        import_path = (directory / migration).resolve()

        log.info(f'Importing migration module from {import_path} ...')

        spec = util.spec_from_file_location(
            migration, import_path,
        )
        module = util.module_from_spec(spec)
        spec.loader.exec_module(module)

        return module

    async def do_migrate(self, to_datetime=None):
        """
        Apply all relevant migrations.

        :param datetime to_datetime: Optional datetime to migrate to.
         Migrations with a timestamp older (less) than this datetime will be
         applied.

        :return list: A list of applied migrations names, sorted in descending
         order (newer first).
        :rtype: list[str]
        """
        if to_datetime is None:
            to_datetime = datetime.now(tz=timezone.utc)

        log.info(f'Executing migration up to {to_datetime.isoformat()} ...')

        files = self._list_fs_migrations()
        migrations_applied = await self._list_db_migrations()

        # Filter migration files to apply only those that are newer (greater)
        # than the latest applied migration
        migrations_to_apply = [
            migration_file.name for migration_file in files
            if (
                not migrations_applied
                or migration_file.name > migrations_applied[0]['name']
            )
        ]

        # Further filter migration files to apply only those that are older
        # (less) than the provided datetime
        if to_datetime:
            migrations_to_apply = [
                migration
                for migration in migrations_to_apply
                if migration < to_datetime.isoformat()
            ]

        if not migrations_to_apply:
            log.info('No migrations need to be applied')
            return migrations_to_apply

        await self._create_metastore_table()
        log.info(f'Applying {len(migrations_to_apply)} migrations ...')

        for migration in migrations_to_apply:
            try:
                log.info(f'-> {migration}')
                module = self._import_module(migration)

                # Execute migration
                migration_obj = module.Migration(self.config)
                txn = await self.db.begin_transaction()
                try:
                    await migration_obj.upgrade(txn)
                    await txn.commit()
                except Exception as e:
                    log.error(
                        'Upgrade function failed, canceling transaction '
                        f'for migration {migration} ...'
                    )
                    await txn.cancel()
                    raise e

                # Insert migration record in metastore
                await self._insert_migration(migration)

            except Exception as e:
                log.error(
                    f'Failed to apply migration {migration}',
                    exc_info=True,
                )

                raise e

        log.info(
            f'Successfully applied {len(migrations_to_apply)} migrations'
        )

        return migrations_to_apply

    async def _delete_migration(self, migration):
        """
        Delete a record of the applied migration from the metastore table.

        :param str migration: The name of the migration to delete.

        :return: The record of the deleted migration.
        :rtype: dict
        """
        table = self.config.migrations.metastore
        query = (
            f'DELETE ONLY {table} '
            'WHERE name = $name RETURN BEFORE;'
        )

        response = await self.db.query(query, {'name': migration})

        record = next(iter(response))
        log.info(
            f'Migration record deleted from metastore {table!r}:\n{record}'
        )
        return record

    async def do_rollback(self, to_datetime=None):
        """
        Rollback all relevant migrations.

        :param datetime to_datetime: Optional datetime to rollback to.
         Migrations with a timestamp greater than this datetime will be rolled
         back.

        :return list: A list of rolled back migration names, sorted in
         descending order (newer first).
        :rtype: list[str]
        """
        if to_datetime is None:
            to_datetime = datetime.now(tz=timezone.utc)

        log.info(f'Executing rollback down to {to_datetime.isoformat()} ...')

        migrations_applied = await self._list_db_migrations()

        # Filter applied migrations to rollback only those that are newer
        # (greater)
        migrations_to_rollback = [
            migration['name']
            for migration in migrations_applied
            if migration['name'] > to_datetime.isoformat()
        ]

        if not migrations_to_rollback:
            log.info(
                f'No migrations to rollback to {to_datetime.isoformat()}'
            )
            return []

        log.info(f'Rolling back {len(migrations_to_rollback)} migrations ...')

        for migration in migrations_to_rollback:
            try:
                log.info(f'-> {migration}')
                module = self._import_module(migration)

                # Execute rollback
                migration_obj = module.Migration(self.config)
                txn = await self.db.begin_transaction()
                try:
                    await migration_obj.downgrade(txn)
                    await txn.commit()
                except Exception as e:
                    log.error(
                        'Downgrade function failed, canceling transaction '
                        f'for migration {migration} ...'
                    )
                    await txn.cancel()
                    raise e

                # Delete migration record from metastore
                await self._delete_migration(migration)

            except Exception as e:
                log.error(
                    f'Failed to roll back migration {migration}',
                    exc_info=True,
                )

                raise e

        log.info(
            f'Successfully rolled back {len(migrations_to_rollback)} '
            'migrations'
        )

        return migrations_to_rollback


__all__ = [
    'MigrationsManager',
]
