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

""" Definition of core Wiking modules.

The modules defined here form the Wiking API.  

"""

from wiking import *

import mx.DateTime
from pytis.presentation import Computer, CbComputer

_ = lcg.TranslatableTextFactory('wiking')


class Mapping(Module):
    """Map available URIs to the modules which handle them.

    This is the central point of a Wiking application.

    The Wiking Handler always queries this module to resolve the request URI and return the name of
    the module which is responsible for handling the request.  Futher processing of the request is
    then postponed to this module.  Only the first part of the request uri is used to determine the
    module.  Other parts (after the first slash) are usually used by the module to determine the
    objects refered or whatever logic the module implements.

    The default implementation uses static mapping defined by the class constant =\_MAPPING=.  The
    value is a dictionary, where keys are uri's and values are the names of the responsible modules
    as strings.

    Apart from the =\_MAPPING= constant, you will need to redefine the method menu().  Other methods
    are implemented within the default class, so you only need to re-implement them if you want to
    replace the static mapping by a more complicated logic.

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
    """Apply specific configuration.

    Configuration is normally read from configuration files as described in the documentation of
    'config_file' configuration option.  This module, however, may update the configuration object
    dynamically at runtime for each request.

    """
    def configure(self, req):
        """Update the configuration object if needed.

        This method is called at an early stage of request processing, so all configuration changes
        made here will influence the rest of the process.

        """
        pass


class Panels(Module):
    """Provide a set of panels to be displayed by the side of each page.

    See the Navigation section of the Wiking User's documentation to learn more about panels.  The
    method 'panels()' of this module returns the global list of all panels as 'Panel' instances.
    It is also possible to override the metohd 'panels()' of any single module, to override the set
    of panels just for this module.  These panels will then only be used, when given module is used
    to handle the current request (is mapped for the current uri).

    """
    def panels(self, req, lang):
        """Rerurn the list of 'Panel' instances."""
        if cfg.allow_login_panel:
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
    """List all available languages.

    Wiking allows you to serve content in multiple languages.  The default language is selected
    automatically using the Content Negotiation techique and the user is also able to switch
    between the available languages manually.  The behavior is described in the Navigation section
    of the Wiking User's documentation.
    
    The interface of this module is based on the method 'languages()', which should return the list
    of all languages, which are relevant for this site.

    You should check, whether the translations for all the specified languages are available in the
    gettext catalog for Wiking and also for all the components you are using, such as LCG and
    Pytis.

    """

    def languages(self):
        """Rerurn the list of available languages as the corresponding alpha-2 language codes."""
        return ['en']


class Stylesheets(Module, ActionHandler):
    """Serves available stylesheets.

    The default implementation serves stylesheet files from the wiking resources directory.  You
    will just need to map this module to serve certain uri, such as 'css'.

    """

    _MATCHER = re.compile (r"\$(\w[\w-]*)(?:\.(\w[\w-]*))?")

    def stylesheets(self):
        """Return the list of all available stylesheets as 'lcg.Stylesheet' instances."""
        identifier = self._module('Mapping').get_identifier('Stylesheets')
        return [lcg.Stylesheet('default.css', uri='/'+identifier+'/default.css')]

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
        """Serve the stylesheet from a file."""
        return ('text/css', self._substitute(self._find_file(req.path[1])))


class Authentication(Module):
    """Perform remote user authentication.

    The interface consists of just one method 'authenticate()'.  See its documentation for more
    information.

    The default implementation does nothing, so the authentication process is passed succesfully,
    but no user is authenticated, so any further authorization checking will lead to an error.

    Wiking also provides the module `CookieAuthentication', which implements standard cookie based
    authentication and may be extended to perform login validation against any external source.
    This module should be usefult for most real authentication scenarios.

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

    
        

