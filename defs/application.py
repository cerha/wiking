# -*- coding: iso-8859-2 -*-
# Copyright (C) 2005, 2006 Tomáš Cerha.
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

"""Definice parametrů aplikace a prvků hlavního aplikačního okna."""

import wx
from pytis.form import *
from pytis.presentation import *
from pytis.extensions import *
import wiking.util

def init(resolver):
    pass
    
def default_font_encoding(resolver):
    return wx.FONTENCODING_ISO8859_2    

def menu(resolver):
    pytis.util.set_resolver(wiking.util.WikingResolver())
    __________ = MSeparator()
    return (
        Menu(_("&Systém"), config_menu_items() +
             (MItem(_("Spustit formulář"), hotkey=('Alt-a', 'a'),
                    command=cmd_run_any_form),
              MItem(_("Zkontrolovat datové specifikace"), hotkey=('Alt-a', 'd'),
                    command=cmd_check_menus_defs),
              __________,
              recent_forms_menu(),
              __________,
              MItem(_("Konec"),
                    command=pytis.form.Application.COMMAND_EXIT,
                    hotkey='Alt-x'),         
              )),
        Menu(_("&Obsah"),
             (bf(_("&Mapování"), 'Mapping'),
              df(_("&Stránky"),  'Mapping::Content'),
              bf(_("&Panely"),   'Panels'),
              bf(_("&Novinky"),  'News'),
              bf(_("S&tyly"),    'Stylesheets'),
              )
        ),
        Menu(_("&Správa uživatelů"),
             (bf(_("&Uživatelé"), 'Users'),
              )
        ),
        Menu(_("Číselní&ky"),
             (bf(_("Jazyky"), 'Languages'),
              bf(_("Typy"),   'Types'),
              )
             )
        )

def status_fields(resolver):
    return (('message', None), ('data-changed', 13), ('list-position', 10))
