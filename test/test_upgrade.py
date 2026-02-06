"""
Test migration upgrade for SurrealDB using surrealdb_migrations.
"""

import pytest
from pathlib import Path

from logging import getLogger


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
        name = "test_do_create"

        path = Path(Path(__file__).parent / "migrations").absolute()
        exists = any(path.glob(f"*_{name}.py"))
        assert not exists, "Migration file already exists"

        mgr.do_create(name)
        exists = any(path.glob(f"*_{name}.py"))
        assert exists, "Migration file was not created"


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
        assert result, "User table was not created by migration"


@pytest.mark.asyncio
async def test_downgrade(migrate_manager):
    mgr = migrate_manager

    async with mgr:
        await mgr.do_migrate()
        result_1 = await mgr.db.query("INFO FOR TABLE user;")
        await mgr.do_rollback()

        # After downgrade, table should be gone
        with pytest.raises(Exception):
            result_2 = await mgr.db.query("INFO FOR TABLE user;")

            assert result_1 != result_2