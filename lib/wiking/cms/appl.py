# -*- coding: utf-8 -*-
# Copyright (C) 2006, 2007, 2008 Brailcom, o.p.s.
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

from wiking.cms import *

_ = lcg.TranslatableTextFactory('wiking-cms')

class Roles(Roles):
    """CMS specific user roles."""
    
    CONTRIBUTOR = 'CONTRIBUTOR'
    """A user hwo has contribution privilegs for certain types of content."""
    AUTHOR = 'AUTHOR'
    """Any user who has the authoring privileges."""


class Application(CookieAuthentication, wiking.Application):
    
    _MAPPING = {'_doc': 'Documentation',
                '_wmi': 'WikingManagementInterface',
                '_css': 'Stylesheets',
                '_resources': 'Resources',
                '_registration': 'Registration'}

    _RIGHTS = {'Documentation': (Roles.ANYONE,),
               'Stylesheets': (Roles.ANYONE,),
               'Resources': (Roles.ANYONE,),
               'SiteMap': (Roles.ANYONE,),
               'WikingManagementInterface': (Roles.AUTHOR, )}

    def handle(self, req):
        req.wmi = False # Will be set to True by `WikingManagementInterface' if needed.
        try:
            self._module('Config').configure(req)
        except MaintananceModeError:
            pass
        if req.unresolved_path:
            try:
                modname = self._MAPPING[req.unresolved_path[0]]
            except KeyError:
                modname = 'Pages'
            else:            
                del req.unresolved_path[0]
            return req.forward(self._module(modname))
        else:
            return super(Application, self).handle(req)

    def module_uri(self, modname):
        try:
            uri = self._module('Pages').module_uri(modname)
        except MaintananceModeError:
            uri = None
        return uri or super(Application, self).module_uri(modname)
        
    def menu(self, req):
        module = req.wmi and 'WikingManagementInterface' or 'Pages'
        try:
            return self._module(module).menu(req)
        except MaintananceModeError:
            return ()
    
    def panels(self, req, lang):
        if req.wmi:
            return ()
        else:
            if cfg.appl.allow_login_panel:
                panels = [LoginPanel()]
            else:
                panels = []
            #if Roles.check(req, (Roles.AUTHOR,)) and hasattr(req, 'page'):
            #    panel = self._module('Pages').content_management_panel(req, req.page)
            #    if panel:
            #        panels.append(panel)
            try:
                return panels + self._module('Panels').panels(req, lang)
            except MaintananceModeError:
                return ()
        
    def languages(self):
        try:
            return self._module('Languages').languages()
        except MaintananceModeError:
            return ('en', 'cs')
        
    def stylesheets(self):
        try:
            styles = self._module('Styles').stylesheets()
        except MaintananceModeError:
            styles = ('default.css',)
        return ['/_css/'+ name for name in styles]

    def _auth_user(self, req, login):
        try:
            return self._module('Users').user(req, login)
        except MaintananceModeError:
            return None
    
    def _auth_check_password(self, user, password):
        return password == user.data()['password'].value()

    def authenticate(self, req):
        user = None
        if cfg.certificate_authentication:
            certificate = req.certificate()
            if certificate is not None:
                user = self._module('UserCertificates').certificate_user(req, certificate)
                if user is not None:
                    user.set_authentication_parameters(method='certificate', auto=True)
        if user is None:
            user = super(Application, self).authenticate(req)
        return user

    def authorize(self, req, module, action=None, record=None, **kwargs):
        if req.path[0] == '_registration':
            # This hack redirects action authorization back to Registration after redirection to
            # Users.
            module = Registration
        if action and hasattr(module, 'RIGHTS_'+action):
            roles = getattr(module, 'RIGHTS_'+action)
        else:
            roles = self._RIGHTS.get(module.name(), ())
        if module.name() == 'Pages' and record and record['private'].value():
            roles = tuple([r == Roles.ANYONE and Roles.USER or r for r in roles])
        #debug("***:", module.name(), action, record.__class__, roles, hasattr(req, 'page'))
        if Roles.check(req, roles):
            return True
        elif Roles.OWNER in roles and module.name() == 'Attachments' and hasattr(req, 'page') \
                 and req.user():
            return self._module('Pages').check_owner(req.user(), req.page)
        elif Roles.OWNER in roles and isinstance(module, PytisModule) and record and req.user():
            return module.check_owner(req.user(), record)
        else:
            return False
        
    def registration_uri(self, req):
        if cfg.appl.allow_registration:
            return make_uri(req.uri_prefix() + self.module_uri('Registration'), action='insert')
        return None
        
    def password_reminder_uri(self, req):
        return make_uri(req.uri_prefix() + self.module_uri('Registration'), action='remind')
        
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
        elif errstr == 'Nen\xed mo\xbeno zjistit typ sloupce':
            if not req.param('initdb'):
                err = self._try_query(dbname, "select * from mapping")
                if err:
                    return 'Database "%s" not initialized!' % dbname + \
                           _button("Initialize", initdb=1)
            else:
                script = ''
                for f in ('wiking.sql', 'init.sql'):
                    path = os.path.join(cfg.wiking_dir, 'sql', f)
                    if os.path.exists(path):
                        script += "".join(file(path).readlines())
                    else:
                        return ("File %s not found! " % path +
                                "Was Wiking installed properly? "
                                "Try setting-up wiking_dir in %s" %
                                cfg.config_file)
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


    
