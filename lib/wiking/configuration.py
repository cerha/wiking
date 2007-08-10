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
_ = lcg.TranslatableTextFactory('wiking-cms')

class Configuration(pc):
    """Wiking Configuration.

    Wiking first tries to import a module named 'wikingconfig'.  If no such module exists in
    the current Python path, the following files are searched in given order:
    
      * /etc/wiking.py
      * /etc/wiking/config.py
      * /usr/local/etc/wiking.py
      * /usr/local/etc/wiking/config.py

    This allows you to use a separate configuration for each website (Python path can be set up
    separately for each Apache virtual host) or share a common configuration file by all hosts.
      
    The configuration file uses Python syntax to assign values to configuration options.  The
    supported options are described below.  Options, which are not found in the configuration file
    will retain their default value (listed below for each option).

    Please note, that Wiking CMS uses the same configuration options, but many of them are
    controlled through the Wiking Management Interface.  These will override the options defined in
    the configuration file.

    """
    class _Option_config_file(pc.StringOption, pc.HiddenOption):
        _DESCR = "Configuration file location"
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
        _DESCR = "Base directory for Wiking shared files"
        _DEFAULT = '/usr/local/share/wiking'
        
    class _Option_storage(pc.StringOption):
        _DESCR = "Directory for storing uploaded files"
        _DOC = ("You only need this directory if you want to use modules which require file "
                "upload, such as Attachments or Images.  The directory must be writable by the "
                "webserver user.")
        _DEFAULT = '/var/lib/wiking'
        
    class _Option_smtp_server(pc.StringOption):
        _DESCR = "Name or address of SMTP server"
        _DOC = ("SMTP server is used for sending bug reports by e-mail.  To allow this feature, "
                "you must also supply the 'bug_report_address' option.")
        _DEFAULT = 'localhost'
        
    class _Option_bug_report_address(pc.StringOption):
        _DESCR = _("E-mail address for sending bug reports")
        _DOC = _("Tracebacks of uncaught exceptions may be sent automatically to the site "
                 "maintainer by e-mail.  Empty value disables this feature.  The tracebacks "
                 "are logged on the server in any case.")
        _DEFAULT = None

    class _Option_https_ports(pc.Option):
        _DESCR = "Sequence of port numbers using HTTPS"
        _DOC = ("If you use HTTPS on some other ports, add them to this list, otherwise some "
                "links may be broken (such as in RSS feeds).")
        _DEFAULT = (443,)
        
    class _Option_translation_paths(pc.Option):
        _DESCR = "Translation path for each translation domain"
        _DOC = ("The value is a dictionary, where keys are translation domain names and values "
                "are paths to the corresponding locale data directories.  These directories "
                "depend on your installation.  Each directory should contain a subdirectory "
                "'<lang>/LC_MESSAGES' and a file '<domain>.mo' in it, where <lang> is the "
                "language code and <domain> is the corresponding dictionary key.")
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
        _DOC = _("Site title is a short and (hopefully) unique title of the whole website. "
                 "It will appear at the top of every page.")
        _DEFAULT = 'Wiking site'

    class _Option_site_subtitle(pc.Option):
        _DESCR = _("Site subtitle")
        _DOC = _("Site subtitle is an optional more descriptive title of the website.  It will "
                 "appear at the top of every page together with site title, but where brevity "
                 "matters, only title will be used.")
        _DEFAULT = None
        
    class _Option_webmaster_addr(pc.Option):
        _DESCR = _("Webmaster's e-mail address")
        _DOC = _("Webmaster's address will appear at the bottom of each page.  If no address is "
                 "given, it will be automatically set to 'webmaster@yourdomain.com', where "
                 "yourdomain.com is replaced by the real name of the server's domain.")
        _DEFAULT = None
        
    class _Option_allow_wmi_link(pc.Option):
        _DESCR = "Allow WMI link in page footer"
        _DOC = ("Set to true to disable the link to the Wiking Management Interface in page "
                "footer.  This is only useful for the Wiking CMS installations.")
        _DEFAULT = False

    class _Option_allow_login_panel(pc.Option):
        _DESCR = _("Allow login panel")
        _DOC = _("If enabled, the information about the currently logged user and login/logout "
                 "controls will appear as a separate panel.  This panel will always be the first "
                 "panel on the page.  If disabled, displaying login controls depends on the "
                 "exporter (the default exporter shows the controls in page footer, which is less "
                 "intrusive, but also harder to find for a new user).")
        _DEFAULT = False
        
    class _Option_allow_login_ctrl(pc.Option):
        _DESCR = "Allow login control"
        _DOC = ("If enabled, and login panel is disabled, the exporter is responsible for "
                "displaying login controls on the page.  The default exporter shows them at "
                "page footer.  This is less intrusive than the login panel, but may be harder "
                "to find for a new user.")
        _DEFAULT = True

    class _Option_allow_registration(pc.Option):
        _DESCR = _("Allow new user registration")
        _DOC = _("If enabled, all visitors are allowed to create a user account.  If disabled, "
                 "new user accounts must be created by administrator.  Note, that the newly "
                 "created accounts are inactive (at least with the default implementation of the "
                 "user management module), so the creation of the account doesn't give the user "
                 "any actual privileges.")
        _DEFAULT = True
        
    class _Option_force_https_login(pc.Option):
        _DESCR = _("Force HTTPS login")
        _DOC = _("If enabled, the login form will always be redirected to an HTTPS address "
                 "to ensure the security of the submitted credentials.  This, however, requires "
                 "your server to be setup to accept HTTPS requests for the same virtualhost and "
                 "pass them to Wiking.")
        _DEFAULT = False

    class _Option_theme(pc.Option):
        _DESCR = "Color theme for stylesheet color substitutions."
        _DEFAULT = Theme()

    class _Option_exporter(pc.Option):
        _DESCR = "Page exporter"
        _DOC = ("Exporter is responsible for rendering the final page.  It gets the logical "
                "description of the page elements on input and outputs its representatio in "
                "HTML/XHTML/XML or any other desired format.  You can make minor page display "
                "customizations, change the layout completely or use another output format by "
                "overriding the exporter.  See LCG documentation for more information about "
                "the export mechanism.")
        _DEFAULT = Exporter()
        
    class _Option_resolver(pc.Option):
        _DESCR = "Module specification resolver"
        _DEFAULT = WikingResolver()

        
