"""
Test migration upgrade for SurrealDB using surrealdb_migrations.
"""

import pytest
from random import randint
from pathlib import Path

from logging import getLogger

from surrealdb_migrations.args import parse_args


log = getLogger(__name__)


@pytest.mark.asyncio
async def test_status(migrate_manager):
    mgr = migrate_manager

    async with mgr:
        # Check Connection works
        result = await mgr.do_status()
        log.info(f"Status result: {result}")

        assert not result

        await mgr.do_migrate()
        qty_upgrade = len(mgr.do_list())

        result = await mgr.do_status()
        log.info(f"Status result after migration: {result}")
        assert len(result) == qty_upgrade


@pytest.mark.asyncio
async def test_create(migrate_manager):
    mgr = migrate_manager

    async with mgr:

        name = f"test_do_create_{randint(1, 1000)}"

        path = Path(Path(__file__).parent / "migrations").absolute()
        exists = any(path.glob(f"*_{name}.py"))
        assert not exists, "Migration file already exists"

        mgr.do_create(name)
        exists = any(path.glob(f"*_{name}.py"))
        assert exists, "Migration file was not created"

        for file in path.glob(f"*_{name}.py"):
            file.unlink()


@pytest.mark.asyncio
async def test_list(migrate_manager):
    mgr = migrate_manager

    async with mgr:
        result = mgr.do_list()
        log.info(f"List of migrations: {result}")

        path = Path(Path(__file__).parent / "migrations").absolute()
        for item in result:
            assert (path / item).exists()


@pytest.mark.asyncio
async def test_upgrade(migrate_manager):
    mgr = migrate_manager

    async with mgr:
        # running all pending up migrations
        await mgr.do_migrate()

        # sanity check: table exists
        result = await mgr.db.query("INFO FOR TABLE user;")
        assert result

        result_email = await mgr.db.query("SELECT email FROM user;")
        assert sorted(result_email, key=lambda x: x['email']) == sorted(
            [
                {'email': 'migration_4@example.com'},
                {'email': 'migration_2@example.com'},
                {'email': 'migration_3@example.com'},
                {'email': 'migration_5@example.com'},
                {'email': 'migration_1@example.com'},
            ],
            key=lambda x: x['email'],
        )



@pytest.mark.asyncio
async def test_downgrade(migrate_manager):
    mgr = migrate_manager

    async with mgr:
        await mgr.do_migrate()
        result_1 = await mgr.db.query("SELECT email FROM user;")
        log.info(f"Result before downgrade: {result_1}")

        await mgr.do_rollback()

        # After downgrade, table should be gone
        result_2 = await mgr.db.query("SELECT email FROM user;")
        log.info(f"Result after downgrade: {result_2}")

        assert result_1 != result_2
        assert result_2 == []

@pytest.mark.asyncio
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