# -*- coding: utf-8 -*-
# Copyright (C) 2006, 2007, 2008, 2009, 2012 Brailcom, o.p.s.
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
import lcg, os

_ = lcg.TranslatableTextFactory('wiking-cms')

class CMSConfiguration(pc):
    """CMS Specific Configuration."""
        
    class _Option_config_file(pc.StringOption, pc.HiddenOption):
        _DESCR = "Global Wiking CMS configuration file location"
        def default(self):
            for filename in ('/etc/wiking/config.py', '/etc/wiking.py',
                             '/usr/local/etc/wiking/config.py', '/usr/local/etc/wiking.py'):
                if os.access(filename, os.F_OK):
                    return filename
            return None

    class _Option_user_config_file(pc.StringOption, pc.HiddenOption):
        _DESCR = "Site specific Wiking CMS configuration file location"
        def default(self):
            try:
                import wikingconfig
            except ImportError:
                return None
            filename = wikingconfig.__file__
            if filename.endswith('.pyc') or filename.endswith('.pyo'):
                filename = filename[:-1]
            return filename
        
    class _Option_allow_login_panel(pc.BooleanOption):
        # Translators: Yes/No configuration option label. Should the login panel be visible?
        _DESCR = _("Allow login panel")
        _DOC = _("If enabled, the information about the currently logged user and login/logout "
                 "controls will be present on each page as a separate panel.  This panel will "
                 "always be the first panel on the page.")
        _DEFAULT = True

    class _Option_allow_wmi_link(pc.BooleanOption):
        # Translators: Yes/No configuration option label. Should link to WMI be visible?  "WMI"
        # stands for Wiking Management Interface.  Don't feel obliged to use an abbreviation.  Use
        # whatever brief form obviously referning to whatever translation you used for "Wiking
        # Management Interface".
        _DESCR = _("Allow WMI link")
        _DOC = ("Set to true to disable the link to the Wiking Management Interface in page "
                "footer.")
        _DEFAULT = True

    class _Option_allow_registration(pc.BooleanOption):
        # Translators: Yes/no configuration label. Can new users register to this
        # website/application?
        _DESCR = _("Allow new user registration")
        _DOC = _("If enabled, all visitors are allowed to create a user account.  If disabled, "
                 "new user accounts must be created by administrator.  Note, that the newly "
                 "created accounts are inactive (at least with the default implementation of the "
                 "user management module), so the creation of the account doesn't give the user "
                 "any actual privileges.")
        _DEFAULT = True

    class _Option_upload_limit(pc.NumericOption):
        # Translators: Maximal size an uploaded file can have.
        _DESCR = _("Maximal upload size")
        _DOC = _("The maximal size of uploaded files in bytes.  The server "
                 "needs to be relaoded for the changes in this option to take effect.")
        _DEFAULT = 3*1024*1024

    class _Option_password_storage(pc.StringOption):
        _DESCR = "Form of storing user passwords in the database"
        _DOC = ("This option defines in which way user passwords are stored in a database. "
                "The allowed values are the strings 'plain' "
                "(passwords are stored in the plain text form), "
                "and 'md5' (passwords are stored in the form of MD5 hashes).")
        _DEFAULT = 'plain'
 
    class _Option_login_is_email(pc.BooleanOption):
        _DESCR = _("Whether to use e-mails as login names")
        _DOC = _("Iff true, users must use e-mail addresses as their login names.")
        _DEFAULT = False
 
