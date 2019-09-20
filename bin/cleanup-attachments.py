#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2018 OUI Technology Ltd.
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

"""Remove stray Wiking CMS attachment files from the filesystem.

Attachments are stored in the filesystem in directory configured by
'wiking.cms.cfg.storage'.  It may happen, that some attachments are removed
from the database but the files remain in the filesystem.  This script will
remove such stray files, for which the corresponding DB record does not exist.

"""

import os
import sys
import getopt

import pytis.util
import pytis.data as pd
import config
import wiking
import wiking.cms

def usage(msg=None):
    sys.stderr.write("""Remove stray attachment files from the filesystem.
Usage: %s [options]
Options:
    --no-act ... Don't actually remove files, only show what would be removed.
    --config PATH ... Path the Wiking CMS configuration file.

Other pytis command line options, such as --dbhost or --dbname may also be used
to override the config file options.

""" % sys.argv[0])
    if msg:
        sys.stderr.write(msg)
        sys.stderr.write('\n')
    sys.exit(1)

def run():
    if '--help' in sys.argv:
        usage()
    if '--no-act' in sys.argv:
        del sys.argv[sys.argv.index('--no-act')]
        no_act = True
    else:
        no_act = False
    try:
        config.add_command_line_options(sys.argv)
        if len(sys.argv) > 1:
            usage()
    except getopt.GetoptError as e:
        usage(e.msg)
    wiking.cfg.user_config_file = config.config_file
    wiking.cms.cfg.user_config_file = config.config_file
    config.dblisten = False
    config.log_exclude = [pytis.util.ACTION, pytis.util.EVENT, pytis.util.DEBUG,
                          pytis.util.OPERATIONAL]
    while True:
        try:
            data = pd.dbtable('cms_page_attachments', ('attachment_id', 'filename'),
                              config.dbconnection)
        except pd.DBLoginException as e:
            if config.dbconnection.password() is None:
                import getpass
                login = config.dbuser
                password = getpass.getpass("Enter database password for %s: " % login)
                config.dbconnection.update_login_data(user=login, password=password)
        else:
            break
    attachments = []
    directory = os.path.join(wiking.cms.cfg.storage, config.dbname, 'attachments')
    ok = stray = 0

    data.select()
    while True:
        row = data.fetchone()
        if row is None:
            break
        ext = os.path.splitext(row['filename'].value())[1].lower()
        fname = row['attachment_id'].export() + (ext or '.')
        path = os.path.join(directory, fname)
        if not os.path.exists(path):
            sys.stderr.write("Missing file: %s\n" % path)
        attachments.append(fname)

    for fname in os.listdir(directory):
        path = os.path.join(directory, fname)
        if os.path.isfile(path):
            if fname in attachments:
                ok += 1
            else:
                stray += 1
                if no_act:
                    sys.stderr.write("Stray file: %s\n" % path)
                else:
                    sys.stderr.write("Removing file: %s\n" % path)
                    os.unlink(path)
    sys.stderr.write("Total %d of %d files ok, %d %s.\n" %
                     (ok, len(attachments), stray, 'stray' if no_act else 'removed'))


if __name__ == '__main__':
    run()
