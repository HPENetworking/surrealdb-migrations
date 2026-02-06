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
from logging import getLogger
from urllib.parse import urlparse, urlunparse


from surrealdb_migrations.config import load_config
from surrealdb_migrations.migrations import MigrationsManager


log = getLogger(__name__)


CONFIG_PATH = Path(__file__).parent / "config.toml"

# -----------------------------
# SurrealDB server fixture
# -----------------------------

CONTAINER_NAME = "surrealdb-test"
IMAGE = "surrealdb/surrealdb:latest"


def load_test_config():
    return Namespace(**loads(CONFIG_PATH.read_text()))


async def wait_for_surreal(health_url, timeout=30):

    start = time.monotonic()
    async with aiohttp.ClientSession() as session:
        while time.monotonic() - start < timeout:
            try:
                async with session.get(health_url, timeout=2) as resp:
                    if resp.status == 200:
                        log.info("SurrealDB Docker is healthy!")
                        return
            except Exception:
                pass

            await asyncio.sleep(5)

    raise RuntimeError(
        f"SurrealDB Docker did not become ready after {timeout:.2f}s"
    )


@fixture
async def surrealdb_server():
    config = load_test_config()
    db = config.database
    url = urlparse(db.url)

    subprocess.run(
        [
            "docker", "run", "-d", "--rm",
            "-p", f"{url.port}:{url.port}",
            "--name", CONTAINER_NAME,
            IMAGE,
            "start",
            # You must bind the RPC server
            "--bind", f"0.0.0.0:{url.port}",
            "--user", db.username,
            "--pass", "root",
            "--log", "info",
            "memory",
        ],
        check=True,
    )

    try:
        log.info(
            "Docker run SurrealDB -> {}:{}".format(url.hostname, url.port)
        )
        await wait_for_surreal(urlunparse(
            url._replace(scheme='http')._replace(path='/health')
        ))
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
    local_config = load_config(CONFIG_PATH)

    # Use a known migrations directory for tests
    local_config['migrations']['directory'] = (
        Path(__file__).parent / "migrations").absolute()

    monkeypatch.setenv("SURREALDB_PASSWORD", "root")
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
                'password': "root",
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
