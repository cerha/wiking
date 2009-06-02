# -*- coding: utf-8 -*-
# Copyright (C) 2006-2009 Brailcom, o.p.s.
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

    _MAPPING = {'doc': 'Documentation',
                'css': 'Stylesheets',
                }
    """Defines static assignment of modules responsible for handling distinct URI paths. 

    The value is a dictionary, where keys are uri's and values are the names of the responsible
    modules as strings.  Only the first part of the request uri is used to determine the module.
    Other parts (after the first slash) may be used by the module for further resolution of the
    request.

    This constant is used by the default implementation of 'Application.handle()'.  See its
    documentation for more information.
    
    """
    
    _STYLESHEETS = ('default.css',)
    
    def __init__(self, *args, **kwargs):
        super(Application, self).__init__(*args, **kwargs)
        self._reverse_mapping = dict([(v,k) for k,v in self._MAPPING.items()])
    
    def handle(self, req):
        """Handle the request.

        The Wiking Handler passes the request to the current application for further processing.
        All errors are handled by the handler.

        The return value may be one of three types:
           * 'Document' instance.
           * The result of `Request.done()' to indicate that the request was already handled.
           * A sequence of two values (MIME_TYPE, CONTENT), where MIME_TYPE is a string determining
             the mime type of the content and CONTENT is the actual output data as an 8-bit string
             or buffer.

        The default implementation uses static mapping defined by the class constant '\_MAPPING' to
        determine which module is responsible for processing the request and passes the request
        along to an instance of this module.  'NotFound' is raised if the mapping doesn't define an
        item for the current request URI.  You may re-implement this method if a different logic is
        more suitable for your application.

        """
        if not req.unresolved_path:
            menu = self.menu(req)
            if menu:
                return req.redirect(menu[0].id())
            else:
                raise Forbidden()
        identifier = req.unresolved_path[0]
        try:
            modname = self._MAPPING[identifier]
        except KeyError:
            raise NotFound()
        module = self._module(modname)
        assert isinstance(module, RequestHandler)
        req.unresolved_path.pop(0)
        return req.forward(module)
    
    def module_uri(self, modname):
        """Return the current uri for given module name.

        The default implementation performes a reverse lookup in the '\_MAPPING' dictionary.  None
        is returned when there is no mapping item for the module, or when there is more than one
        item for the same module (which is also legal).
        
        """
        identitier = self._reverse_mapping.get(modname)
        return identitier and '/'+identitier or None

    def site_title(self, req):
        """Return site title as a string.

        This method returns the value of configuration option 'site_title' by default.  It may
        be overriden to change the title dynamically.
        
        """
        return cfg.site_title

    def site_subtitle(self, req):
        """Return site subtitle as a string or None.

        Site subtitle is normally appended to site title separated by a dash (if not 'None').  It
        is, however, exported in a differnt html element to allow independent styling.

        This method returns the value of configuration option 'site_subtitle' by default.  It may
        be overriden to change the subtitle dynamically.

        """
        return cfg.site_subtitle
    
    def menu(self, req):
        """Return the main navigation menu hierarchy.

        Arguments:
        
          req -- the current request object.

        Returns a sequence of 'MenuItem' instances representing the main menu hierarchy.
        
        The menu structure should usually remains unchanged throughout the application or at least
        throughout its major states, but this is just a common practice, not a requirement.  The
        application may decide to return a different menu for each request.
        
        """
        return ()
                
    def authenticate(self, req):
        """Perform authentication and return a 'User' instance if successful.

        This method is called when authentication is needed.  A 'User' instance must be returned if
        authentication was successful or None if not.  'AuthenticationError' may be raised if
        authentication credentials are supplied but are not correct.  'PasswordExpirationError' may
        be raised if the user is correctly authenticated, but user's 'password_expiration' date is
        today or earlier.  In other cases, None as the returned value means, that the user is not
        logged or that the session expired.

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
    
    def panels(self, req, lang):
        """Return a list of 'Panel' instances representing panels displayed on the page.

        The set of panels will usually be constant throughout the application, but this is just a
        common practice, not a requirement.  The application may decide to return a different set
        of panels for each request.

        Note, that except for the generic 'Panel' class, there are also predefined single purpose
        classes, such as 'LoginPanel'.

        See the Navigation section of the Wiking User's documentation for general information about
        panels.
        
        """
        return []
        
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

    def stylesheets(self, req):
        """Return the list of URIs of all available stylesheets.

        The application is responsible for handling the returned URIs correctly.  Wiking provides a
        generic 'Stylesheets' module for this purpose.

        The default implementation returns the list of stylesheets defined by the '_STYLESHEETS'
        constant of the class.  The filenames defined in this list are automatically prefixed by
        the current mapped uri of the 'Stylesheets' module (if the module is mapped).

        """
        uri = self.module_uri('Stylesheets')
        if uri is not None:
            return [uri +'/'+ file for file in self._STYLESHEETS]
        else:
            return []

    def handle_exception(self, req, exception):
        """Handle exceptions raised during request processing.

        Arguments:
          req -- current request object
          exception -- exception instance

        The application can do any custom error processing within this method, but finally it must
        either handle the request and return a request result or raise an 'InternalServerError'
        exception to signal, that the handler should display an Internal Server Error page with an
        error message.  The error message must be passed to the 'InternalServerError' constructor
        as an argument.

        The default implementation sends a complete exception information (including Python
        traceback) by email if 'cfg.bug_report_address' has been set up.  If not, the traceback is
        logged to server's error log.  'InternalServerError' is then raised.

        """
        import traceback, cgitb
        einfo = sys.exc_info()
        message = ''.join(traceback.format_exception_only(*einfo[:2]))
        try:
            try:
                user = req.user()
            except:
                user = None
            req_info = "\n".join(["%s: %s" % pair for pair in
                                  (("Server", req.server_hostname()),
                                   ("URI", req.uri()),
                                   ("Remote host", req.remote_host()),
                                   ("Remote user", user and user.login() or ''),
                                   ("HTTP referrer", req.header('Referer')),
                                   ("User agent", req.header('User-Agent')),
                                   )])
            text = req_info + "\n\n" + cgitb.text(einfo)
            if cfg.bug_report_address is not None:
                tb = einfo[2]
                while tb.tb_next is not None:
                    tb = tb.tb_next
                filename = os.path.split(tb.tb_frame.f_code.co_filename)[-1]
                buginfo = "%s at %s line %d" % (einfo[0].__name__, filename, tb.tb_lineno)
                pre = req_info + "\n\n" + "".join(traceback.format_exception(*einfo))
                err = send_mail(cfg.bug_report_address, 'Wiking Error: ' + buginfo, text,
                                html="<html><pre>"+ pre +"</pre>"+ cgitb.html(einfo) +"</html>")
                if err:
                    log(OPR, "\n"+ text)
                    log(OPR, "Failed sending traceback by email:", (cfg.bug_report_address, err))
                else:
                    log(OPR, "Exception:", message.strip())
                    log(OPR, "Traceback sent to:", cfg.bug_report_address)
            else:
                log(OPR, "\n"+ text)
        except:
            log(OPR, "Error in exception handling:",
                "".join(traceback.format_exception(*sys.exc_info())))
            log(OPR, "The original exception was", ''.join(traceback.format_exception(*einfo)))
        raise InternalServerError(message)
    
    def registration_uri(self, req):
        """Return the URI for new user registration or None if registration is not allowed."""
        return None

    def password_reminder_uri(self, req):
        """Return the forgotten password link URI or None if password reminder not implemented."""
        return None

    def password_change_uri(self, req):
        """Return the change password URI or None if the link should not appear in login panel."""
        return None

    def login_panel_content(self, req):
        """Return the content displayed in the login panel below the automatically generated part.

        Any content acceptable by 'lcg.coerce()' may be returned.

        """
        return None
    
    def login_dialog_content(self, req):
        """Return the content displayed below the login dialog as 'lcg.Content' element(s).

        Any content acceptable by 'lcg.coerce()' may be returned.

        """
        return None
        
    def _powered_by_wiking(self):
        import wiking
        # Translators: This is followed by Wiking link and version number.
        return (_("Powered by"), ' ',
                lcg.link('http://www.freebsoft.org/wiking', 'Wiking'), ' ', wiking.__version__)
        
    def bottom_bar_left_content(self, req):
        """Return the content displayed on the left side of the bottom bar above the page footer.

        Any content acceptable by 'lcg.coerce()' may be returned.

        """
        return None

    def bottom_bar_right_content(self, req):
        """Return the content displayed on the right side of the bottom bar above the page footer.

        Any content acceptable by 'lcg.coerce()' may be returned.

        """
        return self._powered_by_wiking()

    def footer_content(self, req):
        """Return the content displayed in page footer as 'lcg.Content' element(s).
        
        Any content acceptable by 'lcg.coerce()' may be returned.

        """
        links = [lcg.link(uri, label, descr=descr)
                 for label, uri, descr in
                 (("HTML 4.01",
                   "http://validator.w3.org/check/referer",
                   None),
                  ("CSS2",
                   "http://jigsaw.w3.org/css-validator/check/referer",
                   None),
                  ("WCAG 1.0",
                   "http://www.w3.org/WAI/WCAG1AAA-Conformance",
                   "W3C-WAI Web Content Accessibility Guidelines."),
                  ("Section 508",
                   "http://www.section508.gov",
                   _("US Government Section 508 Accessibility Guidelines.")))]
        doc = self.module_uri('Documentation')
        class A11yStatement(lcg.Content):
            # A11y statement link with a hotkey (not supported by generic lcg links).
            def export(self, context):
                if doc:
                    return ' ' + context.generator().link(_("Accessibility Statement"),
                                                          doc+'/accessibility', hotkey='0')
                else:
                    return ''
        contact = cfg.webmaster_address
        return (lcg.p(_("This site conforms to the following standards:"), ' ',
                      lcg.join(links, separator=', ')),
                lcg.p(_("This site can be viewed in ANY browser."), A11yStatement()),
                lcg.p(_("Contact:"), ' ', lcg.link("mailto:"+ contact, contact)))
    
