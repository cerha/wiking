# -*- coding: utf-8 -*-
#
# Copyright (C) 2012, 2013, 2015 OUI Technology Ltd.
# Copyright (C) 2019, 2026 Tomáš Cerha <cerha@brailcom.org>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Perform incremental migrations of an existing Wiking CMS database.

The script must run under a user having sufficient permissions to modify the
database table.  It runs a sequence of migration scripts in one transaction and
rolls back all changes when one of the scripts fails.

"""
import os
import sys
import glob


def usage(msg=None):
    message = """Perform incremental migrations of an existing Wiking CMS database.
Usage: %s [-p port] database [directory]
  database ... name of the Wiking CMS database to migrate
  directory ... path to Wiking migration scripts; defaults to the 'migrate'
    scripts bundled with this Wiking installation
""" % sys.argv[0]
    if msg:
        message += msg + '\n'
    sys.stderr.write(message)
    sys.exit(1)


def run(args):
    import psycopg2 as dbapi
    if '--help' in args:
        usage()
    if '-p' in args:
        i = args.index('-p')
        try:
            __, port = args.pop(i), int(args.pop(i))
        except (IndexError, ValueError):
            usage("Argument -p requires a number.")
    else:
        port = 5432
    positional = args[1:]
    if len(positional) == 1:
        database = positional[0]
        directory = os.path.join(os.path.dirname(__file__), 'dbdefs', 'migrate')
    elif len(positional) == 2:
        database, directory = positional
    else:
        usage("Invalid number of arguments.")
    if not os.path.isdir(directory):
        usage("Directory '%s' does not exist!" % directory)
    scripts = sorted(glob.glob(os.path.join(directory, 'migrate.*.sql')))
    if not scripts:
        usage("Directory '%s' contains no migration scripts!" % os.path.abspath(directory))
    target_version = int(scripts[-1].split('.')[-2])
    connection = dbapi.connect(database=database, port=port)
    try:
        cursor = connection.cursor()
        cursor.execute("select version from cms_database_version;")
        source_version = cursor.fetchone()[0]
        if source_version == target_version:
            print("The database is already at version %d.\n" % source_version)
            sys.exit(0)
        elif source_version > target_version:
            sys.stderr.write("The database is already at version %d, "
                             "but the highest migration script is %d.\n" %
                             (source_version, target_version))
            sys.exit(1)
        for version in range(source_version + 1, target_version + 1):
            filename = 'migrate.%02d.sql' % version
            sql = open(os.path.join(directory, filename)).read()
            print("Applying %s ..." % filename)
            cursor.execute(sql)
        cursor.execute("update cms_database_version set version=%d;" % target_version)
        connection.commit()
    except Exception as e:
        connection.rollback()
        sys.stderr.write("Error: %s" % e)
        sys.stderr.write("Transaction rolled back.\n")
        sys.exit(1)
    else:
        print("Database %s migrated successfully to version %d." % (database, target_version))
    finally:
        connection.close()


def main():
    run(sys.argv)


if __name__ == '__main__':
    main()
