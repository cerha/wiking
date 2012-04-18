# -*- coding: utf-8 -*-
# Copyright (C) 2006-2012 Brailcom, o.p.s.
# Author: Tomas Cerha.
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

"""Wiking Content Management System implemented as a Wiking application."""

# TODO: Get rid of * imports...
from wiking import *

from configuration import CMSConfiguration
cfg = CMSConfiguration()

import wiking


from cms import *
from users import *
from appl import *
from crypto import *

import texts

_globals = dict([(k,v) for k,v in globals().items() if not k.startswith('_')])
import appl, cms
for _file in (appl, cms):
    _file.__dict__.update(_globals)
