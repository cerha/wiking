#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 Tomáš Cerha <t.cerha@gmail.com>
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

"""Update Wiking CMS user passwords to salted PBKDF2 hashes.

May be optionally applied after upgrade of Wiking CMS database to version 72 to
convert the existing plain text or unsalted md5 passwords to salted PBKDF2 hashes.

"""
import sys
import getopt

import pytis
import pytis.util
import pytis.data as pd
import wiking
import wiking.cms


def usage(msg=None):
    sys.stderr.write("""Update Wiking CMS passwords to salted hashes.
Usage: %s [options]
Options: Pytis command line options, such as --config or --dbhost and --dbname.
""" % sys.argv[0])
    if msg:
        sys.stderr.write(msg)
        sys.stderr.write('\n')
    sys.exit(1)


def run():
    if '--help' in sys.argv:
        usage()
    try:
        pytis.config.add_command_line_options(sys.argv)
        if len(sys.argv) > 1:
            usage()
    except getopt.GetoptError as e:
        usage(e.msg)
    wiking.cfg.user_config_file = pytis.config.config_file
    wiking.cms.cfg.user_config_file = pytis.config.config_file
    pytis.config.dblisten = False
    pytis.config.log_exclude = [pytis.util.ACTION, pytis.util.EVENT,
                                pytis.util.DEBUG, pytis.util.OPERATIONAL]
    while True:
        try:
            data = pd.dbtable('users', ('uid', 'login', 'password'), pytis.config.dbconnection)
        except pd.DBLoginException as e:
            if pytis.config.dbconnection.password() is None:
                import getpass
                login = pytis.config.dbuser
                password = getpass.getpass("Enter database password for %s: " % login)
                pytis.config.dbconnection.update_login_data(user=login, password=password)
        else:
            break
    storage = wiking.Pbkdf2PasswordStorage()
    transaction = pd.transaction()
    data.select(transaction=transaction)
    n = 0
    plain = 0
    try:
        while True:
            row = data.fetchone()
            if row is None:
                break
            orig_prefix, orig_password = row['password'].value().split(':', 1)
            if orig_prefix == 'md5u':
                prefix = 'pbkdf2/md5'
            elif orig_prefix == 'plain':
                prefix = 'pbkdf2'
                plain += 1
            else:
                continue
            password = prefix + ':' + storage.stored_password(orig_password)
            data.update(row['uid'], pd.Row([('password', pd.sval(password))]),
                        transaction=transaction)
            n += 1
    except Exception:
        try:
            transaction.rollback()
        except Exception:
            pass
        sys.stderr.write("Transaction rolled back.\n")
        raise
    else:
        print("Total %d passwords updated (%d from plain text, %d from md5)." % \
            (n, plain, n - plain))
        transaction.commit()
    transaction.close()

if __name__ == '__main__':
    run()
