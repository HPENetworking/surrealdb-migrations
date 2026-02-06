# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 Hewlett Packard Enterprise Development LP.
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

from pathlib import Path
import pprintpp
from pytest import fixture
from logging import getLogger

from surrealdb_migrations.config import load_config
from surrealdb_migrations.migrations import MigrationsManager

log = getLogger(__name__)

# -------------------------------------------------------------------
# Ensure pytest-asyncio plugin is active
# Add this to pytest.ini as well:
#
# [pytest]
# asyncio_mode = auto
# -------------------------------------------------------------------


# -----------------------------
# Async SurrealDB client
# -----------------------------
@fixture
async def migrate_manager(monkeypatch):
    """
    Create a fresh MigrationsManager for each test function.
    Uses a tmp migrations folder so tests don't collide.
    """

    # Monkeypatch config to point to that directory
    local_config =  load_config(Path(__file__).parent / "config.toml")

    monkeypatch.setenv("TEST_MIGRATIONS_DIR", local_config['migrations']['directory'])
    monkeypatch.setenv("SURREALDB_PASSWORD", "root")
    log.info(f"Using testing configuration: {pprintpp.pformat(local_config)}")

    mgr = MigrationsManager(local_config)

    yield mgr

    log.info("Finalizing test module....")
    # cleanup migrations history & applied state
    try:

        log.info("Cleaning test suite....")
        await mgr.db.query(
            f"REMOVE TABLE {local_config['migrations']['metastore']};"
        )
    except Exception:
        raise Exception("Failed to clean up after test suite")
