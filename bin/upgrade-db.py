#!/usr/bin/env python

# Copyright (C) 2012 Brailcom, o.p.s.
#
# COPYRIGHT NOTICE
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
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

import os, sys, psycopg2 as dbapi


def usage(msg=None):
    sys.stderr.write("""Perform incremental upgrades of an existing Wiking CMS database.
Usage: %s database directory source_version target_version
  database ... name of the Wiking CMS database to upgrade
  directory ... path to Wiking upgrade scripts (the `sql' subdirectory of a
    Wiking source archive)
  source_version ... current database version (the upgrade will start with a
    script `upgrade.<source_version+1>.sql
  target_version ... target database version (the upgrade will finish with a
    script `upgrade.<target_version>.sql
""" % sys.argv[0])
    if msg:
        sys.stderr.write(msg)
        sys.stderr.write('\n')
    sys.exit(1)

def run(args):
    if '--help' in args:
        usage()
    try:
        database, directory, source_version, target_version = args[1:]
    except ValueError:
        usage("Invalid number of arguments.")
    try:
        source_version, target_version = int(source_version), int(target_version)
    except ValueError:
        usage("Arguments source_version and target_version must be numbers.")
    if source_version >= target_version:
        usage("The target version must be higher than the source version.")
        
    connection = dbapi.connect(database=database)
    try:
        cursor = connection.cursor()
        for version in range(source_version+1, target_version+1):
            filename = 'upgrade.%02d.sql' % version
            sql = open(os.path.join(directory, filename)).read()
            print "Applying %s ..." % filename
            cursor.execute(sql)
        connection.commit()
        print "Database %s upgraded successfully to version %d." % (database, to)
    except Exception as e:
        connection.rollback()
        sys.stderr.write("Error: %s" % e.message)
        sys.stderr.write("Transaction rolled back.\n")
        sys.exit(1)
    finally:
        connection.close()
    

if __name__ == '__main__':
    run(sys.argv)
