#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2012, 2013, 2015 OUI Technology Ltd.
# Copyright (C) 2019 Tomáš Cerha <t.cerha@gmail.com>
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

"""Perform incremental upgrades of an existing Wiking CMS database.

The script must run under a user having sufficient permissions to modify the
database table.  It runs a sequence of upgrade scripts in one transaction and
rolls back all changes when one of the scripts fails.

"""
import os
import sys
import glob
import psycopg2 as dbapi


def usage(msg=None):
    message = """Perform incremental upgrades of an existing Wiking CMS database.
Usage: %s [-p port] database directory
  database ... name of the Wiking CMS database to upgrade
  directory ... path to Wiking upgrade scripts (the `upgrade' subdirectory of a
    Wiking source archive)
""" % sys.argv[0]
    if msg:
        message += msg + '\n'
    sys.stderr.write(message)
    sys.exit(1)


def run(args):
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
    try:
        database, directory = args[1:]
    except ValueError:
        usage("Invalid number of arguments.")
    if not os.path.isdir(directory):
        usage("Directory '%s' does not exist!" % directory)
    upgrade_scripts = sorted(glob.glob(os.path.join(directory, 'upgrade.*.sql')))
    if not upgrade_scripts:
        usage("Directory '%s' contains no upgrade scripts!" % os.path.abspath(directory))
    target_version = int(upgrade_scripts[-1].split('.')[-2])
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
                             "but the highest upgrade script is %d.\n" %
                             (source_version, target_version))
            sys.exit(1)
        for version in range(source_version + 1, target_version + 1):
            filename = 'upgrade.%02d.sql' % version
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
        print("Database %s upgraded successfully to version %d." % (database, target_version))
    finally:
        connection.close()

if __name__ == '__main__':
    run(sys.argv)
