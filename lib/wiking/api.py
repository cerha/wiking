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

"""Definition of core Wiking modules.

The modules defined here form the Wiking web application programming interface.

"""

from wiking import *

import mx.DateTime
from pytis.presentation import Computer, CbComputer

_ = lcg.TranslatableTextFactory('wiking')


class Mapping(Module):
    """Map available URIs to the modules which handle them.

    The Wiking Handler always queries this module to resolve the request URI and return the name of
    the module which is responsible for handling the request.  Futher processing of the request is
    then postponed to this module.  Only a part of the request uri may be used to determine the
    module and another part may be used by the module to determine the sub-contents.

    This implementation uses static mapping as well as database based mapping, which may be
    modified through the Wiking Management Interface.

    """

    _MAPPING = {'_doc': 'Documentation',
                'css': 'Stylesheets',
                }

    def __init__(self, *args, **kwargs):
        super(Mapping, self).__init__(*args, **kwargs)
        self._reverse_mapping = dict([(v,k) for k,v in self._MAPPING.items()])
    
    def resolve(self, req):
        "Return the name of the module responsible for handling the request."
        identifier = req.path[0]
        try:
            modname = self._MAPPING[identifier]
        except KeyError:
            raise NotFound()
        return modname
    
    def get_identifier(self, modname):
        """Return the current identifier for given module name.

        None will be returned when there is no mapping item for the module, or when there is more
        than one item for the same module (which is also legal).
        
        """
        return self._reverse_mapping.get(modname)
    
    def menu(self, req):
        """Return the menu hierarchy.

        Arguments:
        
          req -- the current request object.
        
        Returns a sequence of 'MenuItem' instances.
        
        """
        return (MenuItem('index', _("Index page")),)
                
    def modtitle(self, modname):
        """Return localizable module title for given module name."""


class Config(Module):
    """Site specific configuration provider.

    Configuration is normally read from configuration files as described in the documentation of
    'Configuration.config_file'.  This module, however, may update the configuration object
    dynamically at runtime for each request.

    """

    def configure(self, req):
        """Update the configuration object if needed."""
        pass


class Panels(Module):
    
    def panels(self, req, lang):
        if cfg.login_panel:
            user = req.user()
            content = lcg.p(LoginCtrl(user))
            if cfg.allow_registration and not user:
                uri = self._module('Users').registration_uri(req)
                if uri:
                    lnk = lcg.link(uri, _("New user registration"))
                    content = lcg.coerce((content, lnk))
            return [Panel('login', _("Login"), content)]
        else:
            return []
    
                
class Languages(Module):
    """List all languages available for given site.

    This implementation stores the list of available languages in a Pytis data
    object to allow their modification through WMI.

    """

    def languages(self):
        """Rerurn the list of available languages as the corresponding alpha-2 language codes."""
        return ['en']


class Stylesheets(Module, ActionHandler):

    _MATCHER = re.compile (r"\$(\w[\w-]*)(?:\.(\w[\w-]*))?")

    def stylesheets(self):
        return [lcg.Stylesheet('default.css', uri='/css/default.css')]

    def _default_action(self, req):
        return 'view'

    def _find_file(self, name):
        filename = os.path.join(cfg.wiking_dir, 'resources', 'css', name)
        if os.path.exists(filename):
            return "".join(file(filename).readlines())
        else:
            raise NotFound()

    def _substitute(self, data):
        theme = cfg.theme
        def subst(match):
            name, key = match.groups()
            value = theme[name]
            if key:
                value = value[key]
            return value
        return self._MATCHER.sub(subst, data)

    def action_view(self, req):
        return ('text/css', self._substitute(self._find_file(req.path[1])))


class Authentication(Module):
    """Abstract class defining the interface of the authentication module.

    The implementing class must be named 'Authentication' and the interface consists of just one
    method 'authenticate()'.  See its documentation for more information.

    """
    def authenticate(self, req):
        """Perform authentication and return a 'User' instance if successful.

        This method is called when authentication is needed by the application.  A 'User' instance
        must be returned if authentication was successful or None if not.  'AuthenticationError'
        may be raised if authentication credentials are supplied but are not correct.  In other
        cases, None as the returned value means, that the user is not logged or that the session
        expired.

        The only argument is the request object, which may be used to obtain authentication
        credentials, store session data (for example as cookies) or whatever else is needed by the
        implemented authentication mechanism.

        """
        return None

    
class CookieAuthentication(Authentication):
    """Authentication class implementing cookie based authentication.

    This class implements cookie based authentication, but is still neutral to authentication data
    source.  Any possible source of authentication data may be used by implementing the methods
    '_user()' and '_check()'.  See their documentation for more information.

    """
    
    _LOGIN_COOKIE = 'wiking_login'
    _SESSION_COOKIE = 'wiking_session_key'

    def _user(self, login):
        """Obtain authentication data and return a 'User' instance for given 'login'.

        This method may be used to retieve authentication data from any source, such as database
        table, file, LDAP server etc.  This should return the user corresponding to given login
        name if it exists.  Further password checking is performed later by the '_check()' method.
        None may be returned if no user exists for given login name.

        """
        return None

    def _check(self, user, password):
        """Check authentication password for given user.

        Arguments:
          user -- 'User' instance
          password -- supplied password as a string

        Return True if given password is the correct login password for given user.

        """
        return False
    
    def authenticate(self, req):
        session = self._module('Session')
        credentials = req.credentials()
        day = 24*3600
        if credentials:
            login, password = credentials
            if not login:
                raise AuthenticationError(_("Enter your login name, please!"))
            if not password:
                raise AuthenticationError(_("Enter your password, please!"))
            user = self._user(login)
            if not user or not self._check(user, password):
                raise AuthenticationError(_("Invalid login!"))
            assert isinstance(user, User)
            # Login succesfull
            session_key = session.init(user)
            req.set_cookie(self._LOGIN_COOKIE, login, expires=730*day)
            req.set_cookie(self._SESSION_COOKIE, session_key, expires=2*day)
        else:
            login, key = (req.cookie(self._LOGIN_COOKIE), 
                          req.cookie(self._SESSION_COOKIE))
            if login and key:
                user = self._user(login)
                if user and session.check(user, key):
                    assert isinstance(user, User)
                    # Cookie expiration is 2 days, but session expiration is
                    # controled within the session module independently.
                    req.set_cookie(self._SESSION_COOKIE, key, expires=2*day)
                else:
                    # This is not true after logout
                    session_timed_out = True
                    user = None
            else:
                user = None
        if req.param('command') == 'logout' and user:
            session.close(user)
            user = None
            req.set_cookie(self._SESSION_COOKIE, None, expires=0)
        elif req.param('command') == 'login' and not user:
            raise AuthenticationError()
        return user

    
class Session(Module):
    _MAX_SESSION_KEY = 0xfffffffffffffffffffffffffffff

    def _new_session_key(self):
        return hex(random.randint(0, self._MAX_SESSION_KEY))
    
    def _expiration(self):
        return mx.DateTime.now().gmtime() + mx.DateTime.TimeDelta(hours=2)

    def _expired(self, time):
        return time <= mx.DateTime.now().gmtime()
    
    def init(self, user):
        return None
        
    def check(self, user, session_key):
	return False

    def close(self, user):
        pass
        

