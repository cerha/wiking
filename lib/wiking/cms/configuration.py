# -*- coding: utf-8 -*-
# Copyright (C) 2006, 2007 Brailcom, o.p.s.
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

"""Wiking CMS configuration.

This configuration class defines the options specific for Wiking Content Management System.  The
supposed usage is as the `appl' option in top level Wiking configuration.

"""

from pytis.util import Configuration as pc
import lcg

_ = lcg.TranslatableTextFactory('wiking-cms')

class CMSConfiguration(pc):
    """CMS Specific Configuration."""
        
    class _Option_allow_login_panel(pc.Option):
        _DESCR = _("Allow login panel")
        _DOC = _("If enabled, the information about the currently logged user and login/logout "
                 "controls will be present on each page as a separate panel.  This panel will "
                 "always be the first panel on the page.")
        _DEFAULT = True

    class _Option_allow_wmi_link(pc.Option):
        _DESCR = _("Allow WMI link")
        _DOC = ("Set to true to disable the link to the Wiking Management Interface in page "
                "footer.")
        _DEFAULT = True

    class _Option_allow_registration(pc.Option):
        _DESCR = _("Allow new user registration")
        _DOC = _("If enabled, all visitors are allowed to create a user account.  If disabled, "
                 "new user accounts must be created by administrator.  Note, that the newly "
                 "created accounts are inactive (at least with the default implementation of the "
                 "user management module), so the creation of the account doesn't give the user "
                 "any actual privileges.")
        _DEFAULT = True


    class _Option_upload_limit(pc.NumericOption):
        _DESCR = _("Maximal upload size")
        _DOC = _("The maximal size of uploaded files in bytes.  The default is 3MB.  The server "
                 "needs to be relaoded for the changes in this option to take effect.")
        _DEFAULT = 3*1024*1024
