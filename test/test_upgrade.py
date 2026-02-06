# -*- coding: utf-8 -*-
"""
Test migration upgrade for SurrealDB using surrealdb_migrations.
"""

import os
import pytest
from surrealdb_migrations.migrations import MigrationsManager
from surrealdb_migrations.config import load_config
import asyncio

TEST_CONFIG = os.path.join(os.path.dirname(__file__), "config", "config.toml")

@pytest.mark.asyncio
async def test_migration_upgrade():
	# Set required environment variable for SurrealDB password
	os.environ["SURREALDB_PASSWORD"] = "test"  # Set to your test password
	config = load_config(TEST_CONFIG)
	mgr = MigrationsManager(config)
	async with mgr:
		# This will run all unapplied migrations in the test/migrations directory
		await mgr.do_migrate()
	# If no exception, test passes (further asserts can be added for state)
