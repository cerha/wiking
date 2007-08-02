# Copyright (C) 2006, 2007 Brailcom, o.p.s.
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

from wiking import *

pc = pytis.util.Configuration

class Configuration(pc):
    
    class _Option_config_file(pc.StringOption, pc.HiddenOption):
        _DESCR = _("Configuration file location")
        _DOC = _("Since this option presents the chicken/egg problem, there are more ways you "
                 "can influence it.  Wiking first tries to import a module named 'wikingconfig'. "
                 "If no such module exists in the current Python path, the following files are "
                 "searched in given order: /etc/wiking.py, /etc/wiking/config.py, "
                 "/usr/local/etc/wiking.py, /usr/local/etc/wiking/config.py.")
        def default(self):
            try:
                import wikingconfig
            except ImportError:
                pass
            else:
                return wikingconfig.__file__
            for filename in ('/etc/wiking.py', '/etc/wiking/config.py',
                             '/usr/local/etc/wiking.py', '/usr/local/etc/wiking/config.py'):
                if os.access(filename, os.F_OK):
                    return filename
            return None
        
    class _Option_wiking_dir(pc.StringOption):
        _DESCR = _("Base directory for Wiking shared files")
        _DEFAULT = '/usr/local/share/wiking'
        
    class _Option_storage(pc.StringOption):
        _DESCR = _("Directory for storing uploaded files")
        _DEFAULT = '/var/lib/wiking'
        
    class _Option_smtp_server(pc.StringOption):
        _DESCR = _("Name or address of SMTP server")
        _DOC = _("SMTP server is used for sending bug reports by e-mail. "
                 "To allow this feature, you must also supply the "
                 "'bug_report_address' option.")
        _DEFAULT = 'localhost'
        
    class _Option_bug_report_address(pc.StringOption):
        _DESCR = _("E-mail address for sending bug reports")
        _DOC = _("Empty value (None) disables sending bug reports by e-mail.")
        _DEFAULT = None

    class _Option_https_ports(pc.Option):
        _DESCR = _("Sequence of port numbers using HTTPS")
        _DOC = _("If you use HTTPS on some other ports, add them to this "
                 "list, otherwise some links may be broken (such as in RSS "
                 "feeds).")
        _DEFAULT = (443,)
        
    class _Option_translation_paths(pc.Option):
        _DESCR = _("Dictionary of translation paths for each translation domain")
        def default(self):
            import os
            dir = os.path.join(self._configuration.wiking_dir, 'translations')
            return {
                'wiking': dir,
                'wiking-cms': dir,
                'lcg':  '/usr/local/share/lcg/translations',
                'lcg-locale':  '/usr/local/share/lcg/translations',
                'pytis': '/usr/local/share/pytis/translations',
                }

    class _Option_site_title(pc.Option):
        _DESCR = _("Site title")
        _DEFAULT = 'Wiking site'

    class _Option_site_subtitle(pc.Option):
        _DESCR = _("Site subtitle")
        _DEFAULT = None
        
    class _Option_allow_wmi_link(pc.Option):
        _DESCR = _("Allow WMI link")
        _DEFAULT = True

    class _Option_allow_login_ctrl(pc.Option):
        _DESCR = _("Allow login control")
        _DEFAULT = True

    class _Option_allow_registration(pc.Option):
        _DESCR = _("Allow registration")
        _DEFAULT = True
        
    class _Option_login_panel(pc.Option):
        _DESCR = _("Allow login panel")
        _DEFAULT = False
        
    class _Option_webmaster_addr(pc.Option):
        _DESCR = _("Webmaster e-mail address")
        _DEFAULT = None
        
    class _Option_force_https_login(pc.Option):
        _DESCR = _("Force HTTPS login")
        _DEFAULT = False
        
    class _Option_theme(pc.Option):
        _DESCR = _("Color theme")
        _DEFAULT = Theme()

    class _Option_exporter(pc.Option):
        _DESCR = _("Exporter")
        _DEFAULT = Exporter()
        
    class _Option_resolver(pc.Option):
        _DESCR = _("Resolver")
        _DEFAULT = WikingResolver()

        
