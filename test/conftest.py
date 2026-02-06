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
from asyncio import sleep
from subprocess import run
from time import monotonic
from logging import getLogger
from urllib.parse import urlparse, urlunparse

from pytest import fixture
from pprintpp import pformat
from aiohttp import ClientSession
from surrealdb import NotFoundError

from surrealdb_migrations.config import load_config
from surrealdb_migrations.migrations import MigrationsManager


log = getLogger(__name__)


CONFIG_PATH = Path(__file__).parent / 'config.toml'

CONTAINER_NAME = 'surrealdb-test'
IMAGE = 'surrealdb/surrealdb:latest'


async def wait_for_surreal(health_url, timeout_s=30):
    start = monotonic()
    async with ClientSession() as session:
        while monotonic() - start < timeout_s:
            try:
                async with session.get(health_url, timeout=2) as resp:
                    log.info(f'Health check response: {resp.status}')
                    if resp.status == 200:
                        log.info('SurrealDB Docker is healthy!')
                        return
            except Exception as e:
                log.warning(f'Health check failed: {e}')
                pass

            await sleep(5)

    raise RuntimeError(
        f'SurrealDB Docker did not become ready after {timeout_s:.2f}s'
    )


@fixture
async def surrealdb_server():
    config = load_config(CONFIG_PATH)
    db = config.database
    url = urlparse(db.url)

    log.info(
        f'Starting a SurrealDB Docker container {CONTAINER_NAME} ...'
    )
    run(
        [
            'docker', 'run', '-d', '--rm',
            '-p', f'{url.port}:{url.port}',
            '--name', CONTAINER_NAME,
            IMAGE,
            'start',
            # You must bind the RPC server
            '--bind', f'0.0.0.0:{url.port}',
            '--user', db.username,
            '--pass', 'root',
            '--log', 'info',
            'memory',
        ],
        check=True,
    )

    log.info(
        'Waiting for SurrealDB Docker to become healthy at '
        f'{url.hostname}:{url.port} ...'
    )
    try:
        await wait_for_surreal(urlunparse(
            url._replace(scheme='http')._replace(path='/health')
        ))
        yield
    finally:
        log.info('Stopping SurrealDB Docker container ...')
        run(
            ['docker', 'stop', CONTAINER_NAME],
            check=False,
        )


@fixture
async def migrate_manager(monkeypatch, surrealdb_server):
    """
    Create a fresh MigrationsManager for each test function.
    """

    # Monkeypatch config to point to that directory
    local_config = load_config(CONFIG_PATH)

    # Use a known migrations directory for tests
    local_config['migrations']['directory'] = str((
        Path(__file__).parent / 'migrations'
    ).resolve())

    monkeypatch.setenv('SURREALDB_PASSWORD', 'root')
    log.info(f'Using TEST configuration: {pformat(local_config)}')

    mgr = MigrationsManager(local_config)
    yield mgr

    async with mgr:
        log.info('Cleaning up test suite ...')
        try:
            await mgr.db.query(
                f'REMOVE TABLE {local_config["migrations"]["metastore"]};'
            )
        except NotFoundError:
            # If the table doesn't exist, that's fine - it means we didn't
            # create it in the test or it was already cleaned up
            pass
