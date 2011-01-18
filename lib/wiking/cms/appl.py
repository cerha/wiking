# -*- coding: utf-8 -*-
# Copyright (C) 2006, 2007, 2008, 2009, 2010, 2011 Brailcom, o.p.s.
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

"""Wiking Content Management System application definition.

The CMS application is defined as an implementation of Wiking Application Interface.

"""

import pytis.data as pd
from wiking.cms import *

_ = lcg.TranslatableTextFactory('wiking-cms')

import time

class Application(CookieAuthentication, wiking.Application):
    
    _MAPPING = {'_doc': 'Documentation',
                '_wmi': 'WikingManagementInterface',
                '_css': 'Stylesheets',
                '_resources': 'Resources',
                '_registration': 'Registration',
                'favicon.ico': 'SiteIcon'}

    _RIGHTS = {'Documentation': (Roles.ANYONE,),
               'Stylesheets': (Roles.ANYONE,),
               'Resources': (Roles.ANYONE,),
               'SiteMap': (Roles.ANYONE,),
               'SiteIcon': (Roles.ANYONE,),
               'WikingManagementInterface': (Roles.USER_ADMIN, Roles.CONTENT_ADMIN,
                                             Roles.SETTINGS_ADMIN, Roles.STYLE_ADMIN,
                                             Roles.MAIL_ADMIN,)}

    _roles_instance = None

    class WMILink(lcg.Content):
        # Used in login panel or bottom bar.
        def export(self, context):
            if not context.req().wmi:
                uri, label, title = ('/_wmi/', _("Manage this site"),
                                     _("Enter the Wiking Management Interface"))
            else:
                uri, label, title = ('/', _("Leave the Management Interface"), None)
            return context.generator().link(label, uri, title=title, hotkey="9", id='wmi-link')

    def handle(self, req):
        req.wmi = False # Will be set to True by `WikingManagementInterface' if needed.
        try:
            self._module('Config').configure(req)
        except MaintenanceModeError:
            pass
        if req.unresolved_path:
            try:
                modname = self._MAPPING[req.unresolved_path[0]]
            except KeyError:
                modname = 'Pages'
            else:            
                # Consume the unresolved path if it was in static mapping or leave it for further
                # resolution when passing to Pages.
                del req.unresolved_path[0]
            return req.forward(self._module(modname))
        else:
            return super(Application, self).handle(req)

    def module_uri(self, req, modname):
        """Return the base URI of given Wiking module (relative to server root).

        This method implements the interface defined by
        'wiking.Application.module_uri()' specifically for the Wiking CMS
        application.


        The method bahaves as follows:

          1. Static mapping as defined by the parent class (see
             'wiking.application._MAPPING') is searched first.  If the module
             is found there, the corresponding path is returned.
          2. Otherwise, if the application is currently in the Wiking
             Management Interface mode, the WMI path is returned as
             '/_wmi/<modname>' (any module is accessible through this path in
             WMI).
          3. If the above fails, the module is searched within CMS pages as
             their extension module.  If the module is found as an extension
             module of a particular page, the path to that page (including the
             subpath to the module) is returned.  Beware that if the same
             module had been used as an extension module for more than one
             page, there would be no way to distinguish which page to use to
             form the path and thus None is returned in such cases.
          4. If the above fails and the module is derived from
             'CMSExtensionModule', its parent module is searched according to
             3. and if found, the corresponding path plus the path to the
             submodule is returned.
          5. If the above fails and the module is accessible through WMI menu,
             the WMI uri is returned (not that as opposed to 2, this happend
             also when we are currently not within WMI).
          6. If all the above fails, None is returned.  Particularly, this
             happens for modules, which are not directly associated with any
             page, which may also be the case for modules accessible through
             bindings to other modules.

         The mapping used in step 1. is called static, because it is a
         hardcoded assignment of URIs of modules needed for Wiking CMS to run
         (such as 'Stylesheets', 'Documentation', 'Resources', etc).  The user
         is not able to change this mapping.  The convention is, that URIs in
         the static mapping in Wiking CMS start with an underscore to prevent
         conflicts with user defined URIs (identifiers) of CMS pages (which are
         dynamic from this perspective — the user may change them).

         Examples (calling through 'WikingRequest.module_uri()'):

           req.module_uri('Documentation')

         Returns '/_doc'.
           
           req.module_uri('Planner')

         Returns '/_wmi/Planner' in WMI or '/planner' outside WMI if the module
         'Planner' is used in a page with an identifier 'planner' or None if
         the module 'Planner' is not used in any CMS page or if it is used more
         than once.  The identifier, of course, may be any string the user
         decides to use, not just 'planner'.
         
           req.module_uri('BugComments')

         Returns '/_wmi/BugComments' in WMI or '/bts/bug-comments' outside WMI
         if the module 'WikingBTS' is used in a page with an identifier 'bts'
         ('BugComments' is a submodule of 'WikingBTS' with a static subpath
         'bug-comments').
        
        """
        
        # Try the static mapping first.
        uri = super(Application, self).module_uri(req, modname)
        if uri is None:
            if req.wmi:
                uri = req.uri_prefix() + '/_wmi/'+ modname
            else:
                try:
                    # Try if the module is directly embedded in a page.
                    uri = self._module('Pages').module_uri(req, modname)
                    if uri is None:
                        # If not embeded directly, try if it is a submodule of an embedded module.
                        module = self._module(modname)
                        if isinstance(module, CMSExtensionModule):
                            parent = module.parent()
                            if parent is not None:
                                uri = parent.submodule_uri(req, modname)
                        if uri is None:
                            uri = self._module('WikingManagementInterface').module_uri(req, modname)
                except MaintenanceModeError:
                    pass
        return uri

    def site_title(self, req):
        if req.wmi:
            return _("Wiking Management Interface")
        else:
            return cfg.site_title

    def site_subtitle(self, req):
        if req.wmi:
            return None
        else:
            return cfg.site_subtitle
    
    def menu(self, req):
        module = req.wmi and 'WikingManagementInterface' or 'Pages'
        try:
            return self._module(module).menu(req)
        except MaintenanceModeError:
            return ()
    
    def panels(self, req, lang):
        if cfg.appl.allow_login_panel:
            panels = [LoginPanel()]
        else:
            panels = []
        try:
            return panels + self._module('Panels').panels(req, lang)
        except MaintenanceModeError:
            return []
        
    def languages(self):
        try:
            return self._module('Languages').languages()
        except MaintenanceModeError:
            return ('en', 'cs')
        
    def stylesheets(self, req):
        try:
            return self._module('Styles').stylesheets(req)
        except MaintenanceModeError:
            return super(Application, self).stylesheets(req)

    def _auth_user(self, req, login):
        try:
            return self._module('Users').user(req, login)
        except MaintenanceModeError:
            return None
    
    def _auth_check_password(self, user, password):
        record = user.data()
        password_storage = cfg.password_storage
        if password_storage == 'plain':
            pass
        elif password_storage == 'md5':
            if isinstance(password, unicode):
                password = password.encode('utf-8')
            try:
                from hashlib import md5
            except ImportError:
                from md5 import md5
            password = md5(password).hexdigest()
        else:
            raise Exception("Invalid password storage option", password_storage)
        return password == record['password'].value()

    def authorize(self, req, module, action=None, record=None, **kwargs):
        """Authorization of CMS modules.

        The method defines basic authorization mechanism based on L{user
        roles<wiking.Role>}.  If C{module} defines constant of the form
        C{RIGHTS_}I{ACTION} where I{ACTION} is C{action} value then the
        constant is used for determining user roles which are allowed to
        perform the action.  The constant must be a tuple of L{Role} instances.
        The user is allowed to perform the action iff one of his roles is among
        the roles listed in the constant.  Note that special roles such as
        I{OWNER} or I{USER} can be used in the list.  See L{Roles} for
        information about standard and special roles.
        
        """
        # Am I the only who thinks this method is a gross hack?  The method
        # shouldn't handle specific requirements of the particular modules, the
        # modules should.  -pdm
        if req.path and req.path[0] == '_registration' and module.name() == 'Users':
            # This hack redirects action authorization back to Registration after redirection to
            # Users.
            module = Registration
        if action and hasattr(module, 'RIGHTS_'+action):
            roles = getattr(module, 'RIGHTS_'+action)
        else:
            roles = self._RIGHTS.get(module.name(), ())
        if module.name() == 'Pages' and record:
            if action in ('view', 'rss'):
                role_id = record['read_role_id'].value()
                roles = (self._module('Users').Roles()[role_id],)
            elif action in ('update', 'commit', 'revert', 'attachments'):
                role_id = record['write_role_id'].value()
                roles = (self._module('Users').Roles()[role_id], Roles.CONTENT_ADMIN)
        if module.name() == 'Attachments' and req.page:
            if action in ('view', 'list'):
                role_id = req.page['read_role_id'].value()
                roles = (self._module('Users').Roles()[role_id],)
            elif action in ('insert', 'update', 'delete'):
                role_id = req.page['write_role_id'].value()
                roles = (self._module('Users').Roles()[role_id], Roles.CONTENT_ADMIN)
        #debug("***:", module.name(), action, record.__class__, roles, hasattr(req, 'page'))
        if req.check_roles(roles):
            return True
        elif Roles.OWNER in roles and module.name() == 'Attachments' and hasattr(req, 'page') \
                 and req.user():
            return self._module('Pages').check_owner(req.user(), req.page)
        elif Roles.OWNER in roles and isinstance(module, PytisModule) and record and req.user():
            return module.check_owner(req.user(), record)
        else:
            return False
        
    def contained_roles(self, req, role):
        role_sets = cfg.resolver.wiking_module('RoleSets')
        role_ids = role_sets.included_role_ids(role)
        if self._roles_instance is None:
            self._roles_instance = self._module('Users').Roles()
        roles_instance = self._roles_instance
        result = tuple([roles_instance[role_id] for role_id in role_ids])
        return result
    
    def registration_uri(self, req):
        if cfg.appl.allow_registration:
            return req.make_uri(req.module_uri('Registration'), action='insert')
        return None
        
    def password_reminder_uri(self, req):
        return req.make_uri(req.module_uri('Registration'), action='remind')

    def login_panel_content(self, req):
        if self.authorize(req, WikingManagementInterface):
            return self.WMILink()
        else:
            return None

    def bottom_bar_left_content(self, req):
        result = self._powered_by_wiking(req)
        if not cfg.appl.allow_login_panel:
            link = self._accessibility_statement_link(req)
            if link:
                result = (result, ' | ', link)
        return result
    
    def bottom_bar_right_content(self, req):
        if cfg.appl.allow_login_panel:
            return self._accessibility_statement_link(req)
        elif req.user() is None:
            return self.WMILink()
        elif self.authorize(req, WikingManagementInterface):
            return (LoginCtrl(inline=True), ' ', self.WMILink())
        else:
            return LoginCtrl(inline=True)

    def footer_content(self, req):
        texts = self._module('Texts')
        text = texts.text(req, wiking.cms.texts.footer, lang=req.prefered_language())
        text = text.replace('$webmaster_address', cfg.webmaster_address)
        return lcg.Parser().parse(text)
    
    def _maybe_install(self, req, errstr):
        """Check a DB error string and try to set it up if it is the problem."""
        def _button(label, action='/', **params):
            return ('<form action="%s">' % action +
                    ''.join(['<input type="hidden" name="%s" value="%s">' % x
                             for x in params.items()]) +
                    '<input type="submit" value="%s">' % label +
                    '</form>')
        dbname = cfg.dbname or req.server_hostname()
        if errstr == 'FATAL:  database "%s" does not exist\n' % dbname:
            if not req.param('createdb'):
                return 'Database "%s" does not exist.\n' % dbname + \
                       _button("Create", createdb=1)
            else:
                create = "CREATE DATABASE \"%s\" WITH ENCODING 'UTF8'" % dbname
                err = self._try_query('postgres', create, autocommit=True)
                if err == 'FATAL:  database "postgres" does not exist\n':
                    err = self._try_query('template1', create)
                if err is None:
                    return 'Database "%s" created.' % dbname + \
                           _button("Initialize", initdb=1)
                elif err == 'permission denied to create database\n':
                    return ('The database user does not have permission to create databases. '
                            'You need to create the database "%s" manually. ' % dbname +
                            'Login to the server as the database superuser (most often postgres) '
                            'and run the following command:'
                            '<pre>createdb %s -E UTF8</pre>' % dbname +
                            _button("Continue", initdb=1))
                else:
                    return 'Unable to create database: %s' % err
        elif errstr.startswith("Unknown column '"):
            if not req.param('initdb'):
                err = self._try_query(dbname, "select * from mapping")
                if err:
                    return 'Database "%s" not initialized!' % dbname + \
                           _button("Initialize", initdb=1)
            else:
                script = ''
                for f in ('wiking.sql', 'init.sql'):
                    path = os.path.join(cfg.sql_dir, f)
                    if os.path.exists(path):
                        script += "".join(file(path).readlines())
                    else:
                        return ("File %s not found! " % path +
                                "Was Wiking CMS installed properly sql_dir set in configuration?")
                err = self._try_query(dbname, script)
                if not err:
                    return ("<p>Database initialized. " +
                            _button("Enter Wiking Management Interface", '/_wmi') + "</p>\n"
                            "<p>Please use the default login 'admin' with password 'wiking'.</p>"
                            "<p><em>Do not forget to change your password!</em></p>")
                else:
                    return "Unable to initialize the database: " + err
                
    def _try_query(self, dbname, query, autocommit=False):
        import psycopg2 as dbapi
        try:
            dboptions = dict([(key, value) for key, value in (('database', dbname),
                                                              ('user', cfg.dbuser),
                                                              ('host', cfg.dbhost),
                                                              ('port', cfg.dbport))
                              if value is not None])
            conn = dbapi.connect(**dboptions)
            try:
                if autocommit:
                    from psycopg2 import extensions
                    conn.set_isolation_level(extensions.ISOLATION_LEVEL_AUTOCOMMIT)
                conn.cursor().execute(query)
                conn.commit()
            finally:
                conn.close()
        except dbapi.ProgrammingError, e:
            return e.args[0]

    def handle_exception(self, req, exception):
        if isinstance(exception, pd.DBException):
            try:
                if exception.exception() and exception.exception().args:
                    errstr = exception.exception().args[0]
                else:
                    errstr = exception.message()
                result = self._maybe_install(req, errstr)
                if result is not None:
                    return req.result(result)
            except:
                pass
        return super(Application, self).handle_exception(req, exception)


    
