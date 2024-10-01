====================
Surrealdb Migrations
====================

The SurrealDB migrations tool helps you manage database schema changes and data
migrations for your SurrealDB database. It provides a simple, CLI-based
approach to handle migrations effectively in a Python application environment.


Documentation
=============

    https://github.hpe.com/hpe-networking/surrealdb_migrations


Features
=============
- **Create new migrations**: Generate migration scripts for database schema changes.
- **Run migrations**: Apply migrations to update your database schema and data.
- **Rollback migrations**: Revert changes applied by previous migrations.
- **List migrations**: List all migration scripts that exist in the directory.


Prerequisites
=============

Ensure that SurrealDB is installed and running on your machine or aplication.
Installation instructions are available `here <https://surrealdb.com/install>`_


Install
=======

.. code-block:: sh

    pip3 install surrealdb_migrations


Usage
=====

General Options
---------------

The following options can be applied to any command in the migration tool:

- **`-c` or `--conf`**: Specifies a custom configuration file. Use this option to provide the path to a custom configuration file that defines settings such as where migration scripts are stored.

  .. code-block:: bash

      surrealdb_migrations <command> --conf /path/to/config.toml

Commands
--------

The tool provides several commands to manage migrations:

1. **Creating a Migration**

   To create a new migration file, run:

   .. code-block:: bash

      surrealdb_migrations create "Name of the migration file"

2. **Listing all Migrations**

   To list all the migration files that exist in the directory, run:

   .. code-block:: bash

      surrealdb_migrations list 

   This will output a list of all migration files, including both applied and
   pending migrations.

3. **Applying Migrations**

   To apply all pending migrations, run:

   .. code-block:: bash

       surrealdb_migrations migrate

   This command will apply any migrations that have not yet been run on your SurrealDB instance.

   If you want to apply migrations up to a certain date, use the `--datetime` option:

   .. code-block:: bash

       surrealdb_migrations migrate --datetime=2024-10-01T22:54:50.040825+00:00

   The `--datetime` argument accepts an ISO 8601 date, allowing you to apply all migrations up to the specified date.
   The format is `YYYY-MM-DDTHH:MM:SS.ssssss+00:00` (e.g., `2024-10-01T22:54:50.040825+00:00`).

4. **Rolling Back Migrations**

   To rollback the last applied migration, run:

   .. code-block:: bash

       surrealdb_migrations rollback

   This command will revert the most recently applied migration.

   If you want to rollback to a specific date, use the `--datetime` option:

   .. code-block:: bash

       surrealdb_migrations rollback --datetime=2024-10-01T22:54:50.040825+00:00

   The `--datetime` argument accepts an ISO 8601 date, allowing you to revert
   all migrations applied after the specified date. The format is `YYYY-MM-DDTHH:MM:SS.ssssss+00:00` (e.g., `2024-10-01T22:54:50.040825+00:00`).


Changelog
=========

0.1.0 (2020-02-01)
------------------

New
~~~

- Development preview.


License
=======

::

   Copyright (C) 2024 Hewlett Packard Enterprise Development LP.

   Licensed under the Apache License, Version 2.0 (the "License"); you may not
   use this file except in compliance with the License.
   You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
   WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
   License for the specific language governing permissions and limitations
   under the License.

