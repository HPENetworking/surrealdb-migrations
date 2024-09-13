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
Executable module entry point.

Install this package, then execute the following to run this module::

    python3 -m surrealdb-migrations
"""

from logging import getLogger

from .migrations import MigrationsManager


log = getLogger(__name__)


def main():
    from setproctitle import setproctitle
    setproctitle('surrealdb-migrations')

    # Parse arguments
    from .args import InvalidArguments, parse_args
    try:
        args = parse_args()
    except InvalidArguments:
        return 1

    # Load configuration
    from .config import load_config
    config = load_config(args.conf)

    mgr = MigrationsManager(config)
    log.debug(f'Configuration:\n{config}')
    log.debug(f'Arguments:\n{args}')

    if args.command == 'create':
        mgr.do_create(args.name)
    elif args.command == 'migrate':
        mgr.do_migrate(to_datetime=args.datetime)
    elif args.command == 'rollback':
        mgr.do_rollback(to_datetime=args.datetime)
    else:
        raise RuntimeError(f'Unknown command {args.command}')

    return 0


if __name__ == '__main__':
    exit(main())


__all__ = []
