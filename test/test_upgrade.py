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
Test migration upgrade for SurrealDB using surrealdb_migrations.
"""

from pathlib import Path
from random import randint
from logging import getLogger
from datetime import datetime

from pytest import mark, raises
from surrealdb import NotFoundError

from surrealdb_migrations.args import parse_args


log = getLogger(__name__)


@mark.asyncio
async def test_do_create(migrate_manager):
    mgr = migrate_manager

    async with mgr:
        # Generate a random name for the migration to avoid conflicts with
        # existing files
        name = f'test_do_create_{randint(1, 1000)}'

        # Check that no migration file with the same name already exists
        path = Path(mgr.config.migrations.directory).resolve()
        before = sorted(path.glob(f'*_{name}.py'))
        log.info(
            f'Migration files for {name} found before creation: {before}'
        )
        assert not before, (
            f'Migration file for name {name} already exists: {before}'
        )

        # Create the migration and check that the file is created
        log.info(f'Creating migration with name: {name} ...')
        created = mgr.do_create(name)
        log.info(f'Migration file created: {created}')

        try:
            after = sorted(path.glob(f'*_{name}.py'))
            log.info(
                f'Migration files for {name} found after creation: {after}'
            )
            assert after, (
                f'Migration file for name {name} was not created: {after}'
            )
            assert len(after) == 1, (
                f'Multiple migration files for name {name} were created: '
                f'{after}'
            )
            assert after[0] == created, (
                f'Migration file created {created} does not match expected '
                f'file {after[0]}'
            )

        finally:
            created.unlink()


@mark.asyncio
async def test_do_list(migrate_manager):
    mgr = migrate_manager

    path = Path(mgr.config.migrations.directory).resolve()
    migrations = sorted(path.glob('*.py'))
    log.info(f'Migration files in directory: {migrations}')

    found = mgr.do_list()
    log.info(f'Migrations files found by the manager: {found}')

    # Check order is correct (older first)
    log.info(
        'Checking that migration files are sorted by name (older first) ...'
    )
    assert found == sorted(found), (
        'Migration files found by the manager are not sorted by name (older '
        'first)'
    )

    # Check that the files found by the manager match the actual files in the
    # directory and that the number of files matches
    log.info(
        'Checking that all migration files found by the manager are present '
        'in the directory and that the number of files matches ...'
    )
    assert len(found) == len(migrations), (
        f'Expected {len(migrations)} migration files, but found {len(found)}'
    )
    assert all(f in migrations for f in found), (
        'Not all migration files found by the manager are present in the '
        'directory'
    )


@mark.asyncio
async def test_do_status(migrate_manager):
    mgr = migrate_manager

    async with mgr:
        # Check database is empty and no migrations are applied
        before = await mgr.do_status()
        log.info(f'Status result before migration: {before}')
        assert not before

        # List all migrations and apply them
        to_apply = mgr.do_list()
        log.info(f'Migrations found: {to_apply}')
        applied = await mgr.do_migrate()
        log.info(f'Migrations applied: {applied}')

        # Check all migrations are applied and status reflects that
        after = await mgr.do_status()
        log.info(f'Status result after migration: {after}')
        assert len(to_apply) == len(applied) == len(after)


@mark.asyncio
async def test_do_upgrade(migrate_manager):
    mgr = migrate_manager

    async with mgr:
        # Running all pending up migrations
        await mgr.do_migrate()

        # Check migration-created table exists
        result = await mgr.db.query('INFO FOR TABLE user;')
        log.info(f'INFO FOR TABLE user result: {result}')
        assert result

        # Check migration-created data is present
        result = await mgr.db.query('SELECT email FROM user;')
        log.info(f'SELECT email FROM user result: {result}')
        assert sorted(result, key=lambda user: user['email']) == sorted(
            [
                {'email': 'migration_4@example.com'},
                {'email': 'migration_2@example.com'},
                {'email': 'migration_3@example.com'},
                {'email': 'migration_5@example.com'},
                {'email': 'migration_1@example.com'},
            ],
            key=lambda user: user['email'],
        )


@mark.asyncio
async def test_do_downgrade(migrate_manager):
    mgr = migrate_manager

    async with mgr:
        # Apply all migrations to ensure there are migrations to roll back
        await mgr.do_migrate()

        before = await mgr.db.query(
            'SELECT email FROM user ORDER BY email;'
        )
        log.info(f'Result before downgrade: {before}')
        assert len(before) == 5
        assert before == [
            {'email': 'migration_1@example.com'},
            {'email': 'migration_2@example.com'},
            {'email': 'migration_3@example.com'},
            {'email': 'migration_4@example.com'},
            {'email': 'migration_5@example.com'},
        ]

        # Perform a partial rollback
        rolled = await mgr.do_rollback(
            to_datetime=datetime.fromisoformat('2026-02-13T00:00:00')
        )
        log.info(f'Migrations rolled back: {rolled}')
        assert len(rolled) == 3
        assert rolled == [
            '2026-02-16T16_18_11_543340_00_00_test_migration.py',
            '2026-02-15T16_22_58_175825_00_00_test_do_create.py',
            '2026-02-13T16_17_26_112716_00_00_test_migration.py'
        ]

        partial = await mgr.db.query(
            'SELECT email FROM user ORDER BY email;'
        )
        log.info(f'Result after partial downgrade: {partial}')
        assert len(partial) == 2
        assert partial == [
            {'email': 'migration_1@example.com'},
            {'email': 'migration_2@example.com'},
        ]

        # Perform a full rollback
        rolled = await mgr.do_rollback(
            to_datetime=datetime.fromisoformat('2025-01-01T00:00:00')
        )
        log.info(f'Migrations rolled back: {rolled}')
        assert len(rolled) == 2
        assert rolled == [
            '2026-02-11T16_16_45_667846_00_00_test_migration.py',
            '2026-02-05T17_11_27_944133_00_00_test.py',
        ]

        # Final rollback should have removed all migrations and the table
        # should no longer exist
        with raises(NotFoundError):
            await mgr.db.query(
                'SELECT email FROM user ORDER BY email;'
            )


@mark.asyncio
async def test_steps_datetime(migrate_manager):
    mgr = migrate_manager

    async with mgr:
        args = parse_args([
            "migrate", "--datetime", "2026-02-08"
        ])
        await mgr.do_migrate(to_datetime=args.datetime)
        result_1 = await mgr.db.query("SELECT email FROM user;")
        log.info(f"Result 1 step: {result_1}")

        assert result_1 == [
            {'email': 'migration_1@example.com'}
        ]

        args = parse_args([
            "migrate", "--datetime", "2026-02-12"
        ])
        await mgr.do_migrate(to_datetime=args.datetime)
        result_2 = await mgr.db.query("SELECT email FROM user;")
        log.info(f"Result 2 step: {result_2}")

        assert sorted(result_2, key=lambda x: x['email']) == sorted(
            [
                {'email': 'migration_2@example.com'},
                {'email': 'migration_1@example.com'},
            ],
            key=lambda x: x['email'],
        )

        await mgr.do_migrate()
        result_3 = await mgr.db.query("SELECT email FROM user;")
        log.info(f"Result all step: {result_3}")

        assert sorted(result_3, key=lambda x: x['email']) == sorted(
            [
                {'email': 'migration_4@example.com'},
                {'email': 'migration_2@example.com'},
                {'email': 'migration_3@example.com'},
                {'email': 'migration_5@example.com'},
                {'email': 'migration_1@example.com'},
            ],
            key=lambda x: x['email'],
        )

        args = parse_args([
            "rollback", "--datetime", "2026-02-12"
        ])

        await mgr.do_rollback(to_datetime=args.datetime)
        result_4 = await mgr.db.query("SELECT email FROM user;")

        assert sorted(result_4, key=lambda x: x['email']) == sorted(
            [
                {'email': 'migration_2@example.com'},
                {'email': 'migration_1@example.com'},
            ],
            key=lambda x: x['email'],
        )

        args = parse_args([
            "rollback", "--datetime", "2026-02-06"
        ])

        await mgr.do_rollback(to_datetime=args.datetime)
        result_5 = await mgr.db.query("SELECT email FROM user;")

        assert sorted(result_5, key=lambda x: x['email']) == sorted(
            [
                {'email': 'migration_1@example.com'},
            ],
            key=lambda x: x['email'],
        )
