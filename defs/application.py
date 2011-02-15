# -*- coding: utf-8 -*-
# Copyright (C) 2006, 2007, 2008, 2011 Brailcom, o.p.s.
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

"""Pytis standalone application specification file."""

import wx
from pytis.form import *
from pytis.presentation import *
from pytis.extensions import *
import wiking.util

def init(resolver):
    pass
    
def default_font_encoding(resolver):
    return wx.FONTENCODING_UTF8

def menu(resolver):
    import config
    pytis.util.set_resolver(wiking.util.WikingFileResolver(config.def_dir))
    __________ = MSeparator()
    return (
        Menu(_("&System"), config_menu_items() +
             (MItem(_("Run form"), hotkey=('Alt-a', 'a'),
                    command=cmd_run_any_form),
              MItem(_("Check specifications"), hotkey=('Alt-a', 'd'),
                    command=cmd_check_menus_defs),
              __________,
              recent_forms_menu(),
              __________,
              MItem(_("Exit"),
                    command=pytis.form.Application.COMMAND_EXIT,
                    hotkey='Alt-x'),
              )
        ),
        Menu(_("&Content"),
             (bf(_("&Pages"),   'Pages'),
              bf(_("&Panels"),  'Panels'),
              bf(_("&News"),    'News'),
              )
        ),
        Menu(_("&Appearance"),
             (bf(_("&Styles"),  'Stylesheets'),
              bf(_("&Themes"),  'Themes'),
              )
        ),
        Menu(_("Se&tup"),
             (bf(_("&Users"), 'Users'),
              ef(_("&Configuration"), 'Config',
                 select_row=(pytis.data.Value(pytis.data.Integer(), 0),)),
              bf(_("Languages"), 'Languages'),
              )
        ),
        )

def status_fields(resolver):
    return (('message', None), ('data-changed', 13), ('list-position', 10))
