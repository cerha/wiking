# -*- coding: iso-8859-2 -*-
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

def maybe_install(req, dbconnection, errstr):
    """Check a DB error string and try to set it up if it is the problem.
    
    """
    dbname = dbconnection.database()
    if errstr == 'FATAL:  database "%s" does not exist\n' % dbname:
        if not req.param('createdb'):
            return 'Database "%s" does not exist: ' % dbname + \
                   _button('createdb', "Create")
        else:
            conn = dbconnection.modified(database='postgres')
            create = "CREATE DATABASE \"%s\" WITH ENCODING 'UTF8'" % dbname
            err = _try_query(conn, create, autocommit=True)
            if err == 'FATAL:  database "postgres" does not exist\n':
                conn = dbconnection.modified(database='template1')
                err = _try_query(conn, create)
            if err is None:
                return 'Database "%s" created.' % dbname + \
                       _button('initdb', "Initialize")
            elif err == 'ERROR:  permission denied to create database\n':
                return ('The database user does not have permission to '
                        'create databases.  You need to create the '
                        'database "%s" manually. ' % dbname +
                        'Login to the server as the database superuser (most '
                        'often postgres) and run the following command:' 
                        '<pre>createdb %s -E UTF8</pre>' % dbname)
            else:
                return 'Unable to create database: %s' % err
    elif errstr == "Není možno zjistit typ sloupce":
        if not req.param('initdb'):
            err = _try_query(dbconnection, "select * from mapping")
            if err:
                return "Database not initialized!" + \
                       _button('initdb', "Initialize")
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
            err = _try_query(dbconnection, script)
            if not err:
                return ("Database initialized."
                        '<a href="/_wmi">Enter the management interface</a>')
            else:
                return "Unable to initialize the database: " + err
                
            

    
def _try_query(dbconnection, query, autocommit=False):
    import psycopg2 as dbapi
    kwargs = dict([(k,v) for k,v in (('user',     dbconnection.user()),
                                     ('password', dbconnection.password()),
                                     ('database', dbconnection.database()),
                                     ('host',     dbconnection.host()),
                                     ('port',     dbconnection.port()))
                   if v is not None])
    try:
        try:
            conn = dbapi.connect(**kwargs)
            if autocommit:
                from psycopg2 import extensions
                conn.set_isolation_level(extensions.ISOLATION_LEVEL_AUTOCOMMIT)
            conn.cursor().execute(query)
            conn.commit()
        finally:
            conn.close()
    except dbapi.ProgrammingError, e:
        return e.args[0]

def _button(param, label):
    return ('<form action="/">'
            '<input type="hidden" name="%s" value="1">'
            '<input type="submit" value="%s">'
            '</form>') % (param, label)

