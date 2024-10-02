# -*- coding: utf-8 -*-
#
# Copyright (C) 2024 Hewlett Packard Enterprise Development LP.
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
Argument management module.
"""

from pathlib import Path
from argparse import ArgumentParser
from datetime import datetime, timezone
from logging import (
    ERROR, WARNING, DEBUG, INFO,
    StreamHandler, getLogger, Formatter, basicConfig,
)

from colorlog import ColoredFormatter

from . import __version__


log = getLogger(__name__)


COLOR_FORMAT = (
    '  {thin_white}{asctime}{reset} | '
    '{log_color}{levelname:8}{reset} | '
    '{log_color}{message}{reset}'
)
SIMPLE_FORMAT = (
    '  {asctime} | '
    '{levelname:8} | '
    '{message}'
)
LEVELS = {
    0: ERROR,
    1: WARNING,
    2: INFO,
    3: DEBUG,
}


class InvalidArguments(Exception):
    """
    Typed exception that allows to fail in argument parsing and verification
    without quiting the process.
    """
    pass


def validate_args(args):
    """
    Validate that arguments are valid.

    :param args: An arguments namespace.
    :type args: :py:class:`argparse.Namespace`

    :return: The validated namespace.
    :rtype: :py:class:`argparse.Namespace`
    """

    # Setup logging
    level = LEVELS.get(args.verbosity, DEBUG)

    if not args.colorize:
        formatter = Formatter(
            fmt=SIMPLE_FORMAT, style='{'
        )
    else:
        formatter = ColoredFormatter(
            fmt=COLOR_FORMAT, style='{'
        )

    handler = StreamHandler()
    handler.setFormatter(formatter)

    basicConfig(
        handlers=[handler],
        level=level,
    )

    log.debug('Arguments:\n{}'.format(args))

    # Check configuration file exists
    if args.conf is not None:
        args.conf = Path(args.conf).resolve()

        if not args.conf.is_file():
            raise InvalidArguments(
                'No such file {}'.format(args.conf)
            )

    # Check input datetime
    if args.command in ['migrate', 'rollback']:
        args.datetime = datetime.fromisoformat(args.datetime)

    return args


def parse_args(argv=None):
    """
    Argument parsing routine.

    :param argv: A list of argument strings.
    :type argv: list

    :return: A parsed and verified arguments namespace.
    :rtype: :py:class:`argparse.Namespace`
    """

    parser = ArgumentParser(
        description=(
            'Surrealdb-Migrations - SurrealDB migrations tool'
        )
    )

    # Standard options
    parser.add_argument(
        '-v', '--verbose',
        action='count',
        dest='verbosity',
        default=0,
        help='Increase verbosity level',
    )
    parser.add_argument(
        '--version',
        action='version',
        version='{} {}'.format(
            parser.description,
            __version__,
        ),
    )
    parser.add_argument(
        '--no-color',
        action='store_false',
        dest='colorize',
        help='Do not colorize the log output'
    )

    parser.add_argument(
        '-c', '--conf',
        help='Path to configuration file',
    )

    # Subcommands:
    # surrealdb_migrations -c config.toml create
    # surrealdb_migrations -c config.toml migrate
    # surrealdb_migrations -c config.toml rollback
    subcommands = parser.add_subparsers(
        required=True,
        dest='command',
    )

    create = subcommands.add_parser('create')
    create.add_argument(
        'name',
        help='Name of the migration file',
    )

    subcommands.add_parser('list')
    subcommands.add_parser('status')

    migrate = subcommands.add_parser('migrate')
    migrate.add_argument(
        '--datetime',
        default=datetime.now(tz=timezone.utc).isoformat(),
        help='Migrate database up to the given datetime (ISO8601)',
    )

    rollback = subcommands.add_parser('rollback')
    rollback.add_argument(
        '--datetime',
        default=datetime.now(tz=timezone.utc).isoformat(),
        help='Rollback database down to the given datetime (ISO8601)',
    )

    # Parse and validate arguments
    args = parser.parse_args(argv)

    try:
        args = validate_args(args)
    except InvalidArguments as e:
        log.critical(e)
        raise e

    return args


__all__ = [
    'parse_args',
]
