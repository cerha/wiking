# Copyright (C) 2006 Brailcom, o.p.s.
# Author: Tomas Cerha <cerha@brailcom.org>
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
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

__version__ = '0.4.1'

import sys, os, cgitb

# TODO: this can be removed once it is solved in Pytis...
reload(sys)
sys.setdefaultencoding('iso-8859-2')

import lcg
import pytis
import config

config.dblisten = False
config.db_encoding = 'utf-8'

import pytis.data as pd
import pytis.presentation as pp
import pytis.util, pytis.extensions, pytis.web

from configuration import *
# This is Wiking-specific configuration.  The above is Pytis config.
cfg = Configuration()

from util import *
from module import *
from export import *
from request import *
from install import *

