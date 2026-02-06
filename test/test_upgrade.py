# -*- coding: utf-8 -*-
"""
Test migration upgrade for SurrealDB using surrealdb_migrations.
"""

import pytest

from logging import getLogger


log = getLogger(__name__)


@pytest.mark.asyncio
async def test_migration_upgrade(migrate_manager):
    mgr = migrate_manager

    async with mgr:
        # running all pending up migrations
        await mgr.do_migrate()

        # sanity check: table exists
        result = await mgr.db.query("INFO FOR TABLE user;")
        assert result, "User table was not created by migration"


@pytest.mark.asyncio
async def test_migration_downgrade(migrate_manager):
    mgr = migrate_manager

    async with mgr:
        await mgr.do_migrate()
        await mgr.do_downgrade()

        # After downgrade, table should be gone
        with pytest.raises(Exception):
            await mgr.db.query("INFO FOR TABLE user;")