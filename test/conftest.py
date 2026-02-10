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

import time
import asyncio
import aiohttp
import pprintpp
import subprocess
from tomli import loads
from pathlib import Path
from pytest import fixture
from objns import Namespace
from surrealdb import Surreal
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

CONFIG_PATH = Path(__file__).parent / "config.toml"
SURREALDB_PASSWORD = 'root'

# -----------------------------
# SurrealDB server fixture
# -----------------------------

CONTAINER_NAME = "surrealdb-test"
IMAGE = "surrealdb/surrealdb:latest"


def load_test_config():
    return Namespace(**loads(CONFIG_PATH.read_text()))

async def wait_for_surreal(url, timeout=30):
    # HTTP health probe (best for tests)
    health_url = url.replace("/rpc", "/health").replace("ws://", "http://")

    start = time.time()
    async with aiohttp.ClientSession() as session:
        while time.time() - start < timeout:
            try:
                async with session.get(health_url, timeout=2) as resp:
                    if resp.status == 200:
                        log.info("SurrealDB Docker is healthy!")
                        return
            except Exception:
                pass

            await asyncio.sleep(5)

    raise RuntimeError("SurrealDB Docker did not become ready")

@fixture
async def surrealdb_server():
    config = load_test_config()
    db = config.database

    # Ensure ws://host:port/rpc
    url = db.url
    if not url.endswith("/rpc"):
        url = url.rstrip("/") + "/rpc"

    clean_url = url.replace("ws://", "").replace("http://", "")
    host_port = clean_url.split("/")[0]
    host, port = host_port.split(":")
    port = int(port)
    subprocess.run(
        [
            "docker", "run", "-d", "--rm",
            "-p", f"{port}:{port}",
            "--name", CONTAINER_NAME,
            IMAGE,
            "start",
            # You must bind the RPC server
            "--bind", f"0.0.0.0:{port}",
            "--user", db.username,
            "--pass", SURREALDB_PASSWORD,
            "--log", "info",
            "memory",
        ],
        check=True,
    )

    try:
        log.info(
            "Docker run SurrealDB -> {}:{}".format(host, port)
        )
        await wait_for_surreal(url)
        yield
    finally:
        subprocess.run(
            ["docker", "stop", CONTAINER_NAME],
            check=False,
        )

# -----------------------------
# MigrationsManager fixture
# -----------------------------
@fixture
async def migrate_manager(monkeypatch, surrealdb_server):
    """
    Create a fresh MigrationsManager for each test function.
    Uses a tmp migrations folder so tests don't collide.
    """

    # Monkeypatch config to point to that directory
    local_config =  load_config(Path(__file__).parent / "config.toml")

    # Use a known migrations directory for tests
    local_config['migrations']['directory'] = (
        Path(__file__).parent / "migrations").absolute()

    monkeypatch.setenv("SURREALDB_PASSWORD", SURREALDB_PASSWORD)
    log.info(f"Using TEST configuration: {pprintpp.pformat(local_config)}")

    mgr = MigrationsManager(local_config)

    yield mgr

    log.info("Finalizing test module....")
    # cleanup migrations history & applied state
    try:
        log.info("Cleaning test suite....")
        if mgr.db is not None:

            await mgr.db.signin({
                'username': mgr.config.database.username,
                'password': SURREALDB_PASSWORD,
            })
            await mgr.db.use(
                namespace=mgr.config.database.namespace,
                database=mgr.config.database.database,
            )
            await mgr.db.query(
                f"REMOVE TABLE {local_config['migrations']['metastore']};"
            )
    except Exception:
        raise Exception("Failed to clean up after test suite")
