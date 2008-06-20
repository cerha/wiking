# Copyright (C) 2006, 2007, 2008 Brailcom, o.p.s.
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

_ = lcg.TranslatableTextFactory('wiking-cms')

pc = pytis.util.Configuration

class Configuration(pc):
    """Wiking Configuration.

    Wiking configuration options can be set through configuration files.  There is one global
    configuration file and it is possible to override configuration options for individual site
    through a site specific configuration file.

    The global configuration file is searched in the following locations:

      * /etc/wiking/config.py
      * /etc/wiking.py
      * /usr/local/etc/wiking/config.py
      * /usr/local/etc/wiking.py

    First of the named files which exists is used.

    Site specific configuration file musy be set throuh the web server's virtual host
    configuration.  In the Apache mod_python environment this is usually done by the following
    directive:

    -----
      PythonOption config_file /etc/wiking/sites/mysite.py
    -----

    See [apache] for more details.
    
    The configuration file uses Python syntax to assign values to configuration options.  The
    supported options are described below.  Options, which are not found in one of the the
    configuration files will retain their default value (listed below for each option).

    The configuration files are re-read automatically in runtime whenever the file is modified so
    in general you should not need to reload the server for the changes to take effect.  Some
    options, however, initialize persistent objects and you may need to reload the server in order
    to reaload these persistent objects.

    Please note, that Wiking CMS will override many of the configuration options by values set
    through the Wiking Management Interface.

    """
    class _Option_config_file(pc.StringOption, pc.HiddenOption):
        _DESCR = "Wiking global configuration file location"
        def default(self):
            for filename in ('/etc/wiking/config.py', '/etc/wiking.py',
                             '/usr/local/etc/wiking/config.py', '/usr/local/etc/wiking.py'):
                if os.access(filename, os.F_OK):
                    return filename
            return None

    class _Option_user_config_file(pc.StringOption, pc.HiddenOption):
        _DESCR = "Site specific configuration file location"
        def default(self):
            try:
                import wikingconfig
            except ImportError:
                return None
            filename = wikingconfig.__file__
            if filename.endswith('.pyc') or filename.endswith('.pyo'):
                filename = filename[:-1]
            return filename
        
    class _Option_modules(pc.Option):
        _DESCR = "Wiking module search order"
        _DOC = ("A sequence of names of Python modules (as strings) used to search for Wiking "
                "module class definitions.  The named Python modules will be searched in given "
                "order and they must be available through Python path.")
        _DEFAULT = ('wiking.cms', )
        
    class _Option_dbname(pc.StringOption):
        _DESCR = "Database name"
        _DOC = ("Name of the database to connect to.  If not defined, the server name of the "
                "current virtual host will be used.")

    class _Option_dbhost(pc.StringOption):
        _DESCR = "Database host"
        _DOC = ("If None (default) Wiking will connect to the database through UNIX domain "
                "sockets.  If a hostname or IP address is specified, Wiking will connect "
                "to given host through a network socket.")

    class _Option_dbport(pc.NumericOption):
        _DESCR = "Database port number"

    class _Option_dbuser(pc.StringOption):
        _DESCR = "Database user"
        
    class _Option_maintenance(pc.BooleanOption):
        _DESCR = "Maintenance mode flag"
        _DOC = ("Setting this value to True will tell Wiking to run in the maintenance mode. "
                "This mode is mostly useful for server administration tasks, which require "
                "excluseive access to the database.  Wiking will not attempt to connect to "
                "the database in this mode and will display a polite error message in response "
                "to requests, which would require database access.")
        _DEFAULT = False
        
    class _Option_smtp_server(pc.StringOption):
        _DESCR = "Name or address of SMTP server"
        _DOC = ("SMTP server is used for sending bug reports by e-mail.  To allow this feature, "
                "you must also supply the 'bug_report_address' option.")
        _DEFAULT = 'localhost'
        
    class _Option_bug_report_address(pc.StringOption):
        _DESCR = "E-mail address where bug reports will be sent"
        _DOC = ("Tracebacks of uncaught exceptions are sent automatically by e-mail to the "
                "specified address.  If None, bug reports are not sent by e-mail, but logged to "
                "server's error log.")
        _DEFAULT = None

    class _Option_webmaster_address(pc.StringOption):
        _DESCR = _("Webmaster's e-mail address")
        _DOC = ("Webmaster's address is used as public contact address for the site. It is "
                "displayed at the bottom of each page, in error messages, RSS feeds and so on. "
                "If no address is given, it will be automatically set to 'webmaster@DOMAIN', "
                "where DOMAIN is the domain part of the server hostname if the hostname starts "
                "with 'www.' or the whole server hostname in other cases.  Please make sure "
                "that this address is valid (e-mail sent to it is delivered to a responsible "
                "person).")
        _DEFAULT = None

    class _Option_default_sender_address(pc.StringOption):
        _DESCR = "Default sender address"
        _DOC = ("Wiking will use given e-mail addres in the From field of e-mail messages "
                "it sends (such as automatic notifications, bug-reports etc). "
                "If no address is given, it will be automatically set to 'wiking@DOMAIN', "
                "where DOMAIN is the domain part of the server hostname if the hostname starts "
                "with 'www.' or the whole server hostname in other cases.  Please make sure "
                "that this address is valid (e-mail sent to it is delivered to a responsible "
                "person).")
        _DEFAULT = None        
        
    class _Option_https_port(pc.NumericOption):
        _DESCR = "HTTPS port number"
        _DOC = ("The default HTTPS port is 443 but certain server configurations may require "
                "using a different port.  Set this option if this is your case.")
        _DEFAULT = 443
        
    class _Option_force_https_login(pc.BooleanOption):
        _DESCR = _("Force HTTPS login")
        _DOC = _("If enabled, the login form will always be redirected to an HTTPS address "
                 "to ensure the security of the submitted credentials.  This, however, requires "
                 "your server to be setup to accept HTTPS requests for the same virtualhost and "
                 "pass them to Wiking.")
        _DEFAULT = False

    class _Option_wiking_dir(pc.StringOption):
        _DESCR = "Base directory for Wiking shared files"
        _DEFAULT = '/usr/local/share/wiking'
        
    class _Option_translation_path(pc.Option):
        _DESCR = "Translation search path"
        _DOC = ("The value is a sequence of directory names (strings), where locale data are "
                "searched.  These directories depend on your installation.  Each directory "
                "should contain a subdirectory 'lang/LC_MESSAGES' and a file 'domain.mo' in it, "
                "where lang is the language code and domain is the translation domain name.")
        def default(self):
            return (os.path.join(self._configuration.wiking_dir, 'translations'),
                    '/usr/local/share/lcg/translations',
                    '/usr/local/share/pytis/translations')

    class _Option_resource_path(pc.Option):
        _DESCR = "Resource search path"
        _DOC = ("The value is a sequence of directory names (strings), where resouce files, "
                "such as images, media or scripts are searched.  Each resource type is searched "
                "within the resource specific subdirectory so you should only specify the list "
                "of the base directories.  The directories are searched in given order and "
                "the LCG resource directory (as set in LCG package configuration) is always "
                "used automatically as the last resort.  Setting this option only makes sense "
                "if you are using the 'Resources' module.  Beware that all files located within "
                "the named directories will be directly exposed to the internet!")
        def default(self):
            return (os.path.join(self._configuration.wiking_dir, 'resources'),)
        
    class _Option_storage(pc.StringOption):
        _DESCR = "Directory for storing uploaded files"
        _DOC = ("You only need this directory if your application(s) use the `StoredFileModule' "
                "(Wiking CMS does that).  The directory must be writable by the webserver user.")
        _DEFAULT = '/var/lib/wiking'
        
    class _Option_site_title(pc.StringOption):
        _DESCR = _("Site title")
        _DOC = _("Site title is a short and (hopefully) unique title of the whole website. "
                 "It will appear at the top of every page.")
        _DEFAULT = 'Wiking site'

    class _Option_site_subtitle(pc.StringOption):
        _DESCR = _("Site subtitle")
        _DOC = _("Site subtitle is an optional more descriptive title of the website.  It will "
                 "appear at the top of every page together with site title, but where brevity "
                 "matters, only title will be used.")
        _DEFAULT = None
        
    class _Option_theme(pc.Option):
        _DESCR = "Color theme for stylesheet color substitutions."
        _DEFAULT = Theme()
      
    class _Option_resolver(pc.Option):
        _DESCR = "Wiking module resolver"
        _DOC = ("Module resolver is used to locate available Wiking modules.  The value must be "
                "a 'WikingResolver' instance.  If not set, the default instance will be created "
                "by Wiking handler in the initialization phase using the values of configuration "
                "options 'modules', 'database', 'dbhost', 'dbport', 'dbuser' and 'maintenance' "
                "defined above.  If you supply your own instance, the configured values of the "
                "above named options will have no effect.")
        
    class _Option_exporter(pc.Option):
        _DESCR = "Page exporter class"
        _DOC = ("Exporter is responsible for rendering the final page.  It gets the logical "
                "description of the page elements on input and outputs its representatio in "
                "HTML/XHTML/XML or any other desired format.  You can make minor page display "
                "customizations, change the layout completely or use another output format by "
                "overriding the defaul exporter.  See LCG documentation for more information "
                "about the export mechanism.")
        _DEFAULT = Exporter

    class _Option_registration_expiry_days(pc.Option):
        _DESCR = "Number of days after unanswered user registration expires"
        _DOC = ("When registration by e-mail is enabled, each newly registered user is required "
                "to answer the registration e-mail within the limit given here.")
        _DEFAULT = 2

    class _Option_certificate_expiration_days(pc.Option):
        _DESCR = "Number of days to make signed certificates valid."
        _DOC = ("User authentication certificates signed by our local certificate authority "
                "will be made valid for that number of days.")
        _DEFAULT = 5*365

    class _Option_ca_certificate_file(pc.Option):
        _DESCR = "Name of the file containing the local certification authority certificate."
        _DOC = ("This certificate is used to sign users' certificates used for authentication to the application.")
        _DEFAULT = '/etc/wiking/ca-cert.pem'

    class _Option_ca_key_file(pc.Option):
        _DESCR = "Name of the file containing the key corresponding to the local certification authority certificate."
        _DOC = ("This is the secret certificate private key.")
        _DEFAULT = '/etc/wiking/ca-key.pem'

    class _Option_certificate_authentication(pc.Option):
        _VISIBLE = False
        _DESCR = "Whether certificate authentication is enabled."
        def default(self):
            ca_certificate_file = self._configuration.ca_certificate_file
            return ca_certificate_file and os.path.exists(ca_certificate_file)

    class _Option_login_is_email(pc.BooleanOption):
        _DESCR = _("Whether to use e-mails as login names")
        _DOC = _("Iff true, users must use e-mails as their login names.")
        _DEFAULT = False

    class _Option_appl(pc.Option):
        _DESCR = "Application specific configuration"
        _DOC = ("This option makes it possible to define an application specific set of "
                "configuration options for each Wiking application and make these options "
                "available throught the main configuration instance.  Type of the value is "
                "optional, but an instance of class derived from 'pytis.util.Configuration' is "
                "recommended.")
        
