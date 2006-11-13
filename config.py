# -*- coding: iso-8859-2 -*-
"""Pytis configuration for running a standalone application."""

import getpass, sys

def_dir = '/home/cerha/work/wiking/defs'
help_dir =  '/home/cerha/work/asellus/pytis-help'
icon_dir =  '/home/cerha/work/asellus/pytis/icons'
application_name = 'Wiking'
log_one_line_preferred = True
dbuser = getpass.getuser()
dbname = 'wiking'
dbhost = 'localhost'
db_encoding = 'utf-8'
cache_spec_onstart = False
date_format = '%d.%m.%Y'
date_time_format = '%d.%m.%Y %H:%M:%S'

