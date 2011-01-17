# Copyright (C) 2006, 2007, 2008, 2009, 2010, 2011 Brailcom, o.p.s.
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

__version__ = '1.2.0'

import sys, os, time, string, re, copy, urllib

# TODO: this can be removed once it is solved in Pytis...
reload(sys)
sys.setdefaultencoding('iso-8859-2')

import pytis, pytis.util
import pytis.data as pd
import pytis.presentation as pp
import pytis.web as pw

import lcg
from lcg import log as debug 

from request import *
from util import *
from modules import *
from db import *
from application import *
from export import *

from configuration import *
# Initialize the global configuration object.
cfg = Configuration()

# We don't want to overwrite module's __doc__ and other private identifiers...
_globals = dict([(k,v) for k,v in globals().items() if not k.startswith('_')])
import util, modules, db, application, export, request
for _file in (util, modules, db, application, export, request):
    _file.__dict__.update(_globals)
del _globals

