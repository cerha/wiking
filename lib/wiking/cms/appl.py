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


class Application(CookieAuthentication, Application):
    
    _MAPPING = {'_doc': 'Documentation',
                '_wmi': 'WikingManagementInterface',
                '_css': 'Stylesheets',
                '_registration': 'Registration'}

    _RIGHTS = {'Documentation': (Roles.ANYONE,),
               'SiteMap': (Roles.ANYONE,),
               'WikingManagementInterface': (Roles.AUTHOR, )}

    def resolve(self, req):
        return self._MAPPING.get(req.path[0], 'Pages')
    
    def module_uri(self, modname):
        return self._module('Pages').module_uri(modname) \
               or super(Application, self).module_uri(modname)
        
    def menu(self, req):
        module = req.wmi and 'WikingManagementInterface' or 'Pages'
        return self._module(module).menu(req)
    
    def panels(self, req, lang):
        if req.wmi:
            return ()
        else:
            return super(Application, self).panels(req, lang) + \
                   self._module('Panels').panels(req, lang)
        
    def configure(self, req):
        # TODO: This should be here as soon as req.wmi doesn't appear anywhere outside CMS.
        # req.wmi = False # Will be set to True by `WikingManagementInterface'.
        return self._module('Config').configure(req)
        
    def languages(self):
        return self._module('Languages').languages()
        
    def stylesheets(self):
        return [lcg.Stylesheet(name, uri='/_css/'+name)
                for name in self._module('Stylesheets').stylesheets()]

    def _auth_user(self, login):
        return self._module('Users').user(login)

    def _auth_check_password(self, user, password):
        return password == user.data()['password'].value()

    def authorize(self, req, module, action=None, record=None, **kwargs):
        if req.uri.startswith('/_registration'):
            # This hack redirects action authorization back to Registration after redirection to Users.
            module = Registration
        if action and hasattr(module, 'RIGHTS_'+action):
            roles = getattr(module, 'RIGHTS_'+action)
        else:
            roles = self._RIGHTS.get(module.name(), ())
        if module.name() == 'Pages' and record and record['private'].value():
            roles = tuple([r == Roles.ANYONE and Roles.USER or r for r in roles])
        if Roles.check(req, roles):
            return True
        elif Roles.OWNER in roles and isinstance(module, PytisModule) and record and req.user():
            return module.check_owner(req.user(), record)
        else:
            return False
        
    def registration_uri(self):
        if cfg.allow_registration:
            return make_uri(self.module_uri('Registration'), action='insert')
        return None
        
    def password_reminder_uri(self):
        return make_uri(self.module_uri('Registration'), action='remind')
        
    def _maybe_install(self, req, errstr):
        """Check a DB error string and try to set it up if it is the problem."""
        def _button(label, action='/', **params):
            return ('<form action="%s">' % action +
                    ''.join(['<input type="hidden" name="%s" value="%s">' % x
                             for x in params.items()]) +
                    '<input type="submit" value="%s">' % label +
                    '</form>')
        options = req.options()
        dboptions = dict([(k, options[k]) for k in
                          ('user', 'password', 'host', 'port') if options.has_key(k)])
        dboptions['database'] = dbname = options.get('database', req.server_hostname())
        if errstr == 'FATAL:  database "%s" does not exist\n' % dbname:
            if not req.param('createdb'):
                return 'Database "%s" does not exist.\n' % dbname + \
                       _button("Create", createdb=1)
            else:
                create = "CREATE DATABASE \"%s\" WITH ENCODING 'UTF8'" % dbname
                err = self._try_query(dboptions, create, autocommit=True, database='postgres')
                if err == 'FATAL:  database "postgres" does not exist\n':
                    err = self._try_query(dboptions, create, database='template1')
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
                err = self._try_query(dboptions, "select * from mapping")
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
                err = self._try_query(dboptions, script)
                if not err:
                    return ("<p>Database initialized. " +
                            _button("Enter Wiking Management Interface", '/_wmi') + "</p>\n"
                            "<p>Please use the default login 'admin' with password 'wiking'.</p>"
                            "<p><em>Do not forget to change your password!</em></p>")
                else:
                    return "Unable to initialize the database: " + err
                
    def _try_query(self, dboptions, query, autocommit=False, database=None):
        import psycopg2 as dbapi
        try:
            if database is not None:
                dboptions['database'] = database
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


    
