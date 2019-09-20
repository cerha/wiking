#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2012, 2013, 2015, 2016 OUI Technology Ltd.
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

"""Update and compile source code in GIT repositories found in given directory.

This script simplifies updates of typical Wiking web application deployments
which run from git repositories specific for a particular web server's virtual
host.

All sudbirectories, which are git repositories are updated from git by running
"git pull" and if they contain a makefile, "make" is run as well.  This usually
compiles Python byte code and generates Gettext translations in repositories
typically needed for Wiking web applications (LCG, Pytis, Wiking etc).  Note
that you may need to run upgrade-db.py after this script.

"""
import os
import sys
import subprocess


def usage(message=None):
    text = ["Usage: %s directory" % os.path.basename(sys.argv[0])]
    if message:
        text.append(message)
        text.append("Use --help for more information.")
    else:
        text.append(__doc__.strip())
    sys.stderr.write('\n\n'.join(text) + '\n')
    sys.exit(1)


def call(command, cwd):
    result = subprocess.call(command.split(' '), cwd=cwd)
    if result != 0:
        sys.exit(1)


def update_src(directory):
    if not os.path.isdir(directory):
        usage("Not a directory: %s" % directory)
    repos = [d for d in os.listdir(directory)
             if os.path.isdir(os.path.join(directory, d, '.git'))]
    if not repos:
        usage("No subdirectories found: %s" % os.path.abspath(directory))
    for repo in repos:
        print("Updating repository: %s" % repo)
        subdir = os.path.join(directory, repo)
        call('git pull', subdir)
        if ((os.path.exists(os.path.join(subdir, 'Makefile')) or
             os.path.exists(os.path.join(subdir, 'makefile')))):
            call('make', subdir)

if __name__ == '__main__':
    if '--help' in sys.argv:
        usage()
    if len(sys.argv) != 2:
        usage("Invalid number of arguments.")
    update_src(sys.argv[1])
