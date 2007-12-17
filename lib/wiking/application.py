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

"""Definition of default Wiking application and its API."""

from wiking import *

import mx.DateTime
from pytis.presentation import Computer, CbComputer

_ = lcg.TranslatableTextFactory('wiking')


class Application(Module):
    """Define Wiking application behavior.

    Wiking application is itself a Wiking module.  This module defines the basic application
    behavior.  You may customize your application by overriding this module and implementing the
    methods which form the Application API by your own means.

    """

    _MAPPING = {'_doc': 'Documentation',
                'css': 'Stylesheets',
                }
    
    """Defines static assignment of modules responsible for handling distinct URI paths. 

    The value is a dictionary, where keys are uri's and values are the names of the responsible
    modules as strings.  Only the first part of the request uri is used to determine the module.
    Other parts (after the first slash) may be used by the module for further resolution of the
    request.

    This constant is used by the default implementation of the method 'resolve()'.  See its
    documentation for more information.
    
    """
    
    _STYLESHEETS = ('default.css',)
    
    def __init__(self, *args, **kwargs):
        super(Application, self).__init__(*args, **kwargs)
        self._reverse_mapping = dict([(v,k) for k,v in self._MAPPING.items()])
    
    def resolve(self, req):
        """Return the name of the module responsible for handling the request.

        The Wiking Handler uses this method to determine which module is responsible for processing
        the request (to be able to postpone it to this module).

        The default implementation uses static mapping defined by the class constant '\_MAPPING'.
        You will need to re-implement this method if you want to replace the static mapping by a
        more complicated logic.

        """
        identifier = req.path[0]
        try:
            modname = self._MAPPING[identifier]
        except KeyError:
            raise NotFound()
        return modname
    
    def module_uri(self, modname):
        """Return the current uri for given module name.

        None will be returned when there is no mapping item for the module, or when there is more
        than one item for the same module (which is also legal).  This is in principe a reverse
        function to 'resolve'.
        
        """
        identitier = self._reverse_mapping.get(modname)
        return identitier and '/'+identitier or None
    
    def menu(self, req):
        """Return the main navigation menu hierarchy.

        Arguments:
        
          req -- the current request object.

        Returns a sequence of 'MenuItem' instances representing the main menu hierarchy.
        
        The menu structure should usually remain unchanges throughout the application or at least
        throughout its mojor states, but this is just a common practice, not a requirement.  The
        application may decide to return a different menu for each request.
        
        """
        return ()
                
    def authenticate(self, req):
        """Perform authentication and return a 'User' instance if successful.

        This method is called when authentication is needed.  A 'User' instance must be returned if
        authentication was successful or None if not.  'AuthenticationError' may be raised if
        authentication credentials are supplied but are not correct.  In other cases, None as the
        returned value means, that the user is not logged or that the session expired.

        The only argument is the request object, which may be used to obtain authentication
        credentials, store session data (for example as cookies) or whatever else is needed by the
        implemented authentication mechanism.

        The default implementation does nothing, so the authentication process is passed
        succesfully, but no user is authenticated, so any further authorization checking will lead
        to an error.

        Wiking also provides the `CookieAuthentication' class, which implements standard cookie
        based authentication and may be extended to perform login validation against any external
        source.  This module should be usefult for most real authentication scenarios.

        """
        return None

    def authorize(self, req, module, action=None, record=None, **kwargs):
        """Check authorization of the current user for given action on given module.

        Arguments:
          req -- Current request as a 'Request' instance.
          module -- The module responsible for handling the request as a 'RequestHandler' instance.
          action -- Action name as a string or None for global module access check (this argument
            is only used for 'ActionHandler' modules).
          kwargs -- Action arguments (if any).  Also relevant only for 'ActionHandler' modules.
          
        Returns true if the user is allowed to perform given action and false if not.

        The default implementation always returns True.
        
        """
        return True
    
    def configure(self, req):
        """Update the configuration object if needed.

        Configuration is normally read from configuration files as described in [config].  This
        module, however, may update the configuration object dynamically at runtime for each
        request.

        
        This method is called at an early stage of request processing, so all configuration changes
        made here will influence the rest of the process.

        """
        pass

    def panels(self, req, lang):
        """Return a list of 'Panel' instances representing panels displayed on the page.

        The set of panels will usually be constant throughout the application, but this is just a
        common practice, not a requirement.  The application may decide to return whatever is
        reasonable for the current request.

        See the Navigation section of the Wiking User's documentation for general information about
        panels.
        
        """
        if cfg.allow_login_panel:
            user = req.user()
            content = lcg.p(LoginCtrl(user))
            if user and user.passwd_expiration():
                date = lcg.LocalizableDateTime(str(user.passwd_expiration()))
                content = lcg.coerce((content,
                                      lcg.p(_("Your password expires on %(date)s.", date=date))))
            elif not user:
                uri = self.registration_uri()
                if uri:
                    lnk = lcg.link(uri, _("New user registration"))
                    content = lcg.coerce((content, lnk))
            return [Panel('login', _("Login"), content)]
        else:
            return []
        
    def registration_uri(self):
        """Return the URI for new user registration or None if registration is not allowed."""
        return None
        
    def password_reminder_uri(self):
        """Return the forgotten password link URI or None if password reminder not implemented."""
        return None
        
    def languages(self):
        """Return the list of available languages as the corresponding alpha-2 language codes.
        
        Wiking allows you to serve content in multiple languages.  The default language is selected
        automatically using the Content Negotiation techique and the user is also able to switch
        between the available languages manually.  The behavior is described in the Navigation
        section of the Wiking User's documentation.

        This method returns the list of all languages relevant for the application.
        
        You should check, whether the translations for all the specified languages are available in
        the gettext catalog for Wiking and also for all the components you are using, such as LCG
        and Pytis.


        """
        return ['en']

    def stylesheets(self):
        """Return the list of all available stylesheets as 'lcg.Stylesheet' instances.

        Each of the stylesheets should have the 'uri' set to an existing uri mapped to a module,
        which serves its contents.  Wiking provides a basic 'Stylesheets' module for this purpose.

        The default implementation returns the list of default Wiking stylesheets if the
        'Stylesheets' module is mapped.

        """
        uri = self.module_uri('Stylesheets')
        return [lcg.Stylesheet(file, uri=uri+'/'+file) for file in self._STYLESHEETS]

    def handle_exception(self, req, exception):
        """Handle exceptions raised during request processing.

        Arguments:
          req -- current request object
          exception -- exception instance
          dbconnection -- current database connection specification as 'pd.DBConnection' instance.

        The default implementation sends a complete exception information (including Python
        traceback) by email if 'cfg.bug_report_address' has been set up.  If not, the traceback is
        logged to server's error log.  The exception string (without traceback) is sent to the
        browser with a 501 HTTP return code (Internal Server Error).

        """
        if isinstance(exception, IOError) \
               and str(exception) == "Write failed, client closed connection.":
            return req.done()
        import traceback, cgitb
        einfo = sys.exc_info()
        message = ''.join(traceback.format_exception_only(*einfo[:2]))
        try:
            user = req.user()
        except:
            user = None
        req_info = (("URI", req.uri),
                    ("Remote host", req.remote_host()),
                    ("Remote user", user and user.login() or ''),
                    ("HTTP referrer", req.header('Referer')),
                    ("User agent", req.header('User-Agent')),
                    )
        text = "\n".join(["%s: %s" % pair for pair in req_info]) + \
               "\n\n" + "".join(traceback.format_exception(*einfo))
        try:
            if cfg.bug_report_address is not None:
                tb = einfo[2]
                while tb.tb_next is not None:
                    tb = tb.tb_next
                filename = os.path.split(tb.tb_frame.f_code.co_filename)[-1]
                buginfo = "%s at %s line %d" % (einfo[0].__name__, filename, tb.tb_lineno)
                send_mail('wiking@' + req.server_hostname(), cfg.bug_report_address,
                          'Wiking Error: ' + buginfo,
                          text + "\n\n" + cgitb.text(einfo),
                          "<html><pre>"+ text +"</pre>"+ cgitb.html(einfo) +"</html>")
                log(OPR, message)
                log(OPR, "Traceback sent to:", cfg.bug_report_address)
            else:
                log(OPR, "Error:", cgitb.text(einfo))
        except Exception, e:
            log(OPR, "Error in exception handling:",
                "".join(traceback.format_exception(*sys.exc_info())))
            log(OPR, "The original exception was:", text)
        return req.error(message)
    
