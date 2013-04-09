# -*- coding: utf-8 -*-
# Copyright (C) 2006-2013 Brailcom, o.p.s.
# Author: Tomas Cerha.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
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
                'favicon.ico': 'SiteIcon',
                'robots.txt': 'Robots',
                }
    """Defines static assignment of modules responsible for handling distinct URI paths. 

    The value is a dictionary, where keys are uri's and values are the names of the responsible
    modules as strings.  Only the first part of the request uri is used to determine the module.
    Other parts (after the first slash) may be used by the module for further resolution of the
    request.

    This constant is used by the default implementation of 'Application.handle()' and
    'Application.module_uri()'.  See their documentation for more information.
    
    """
    
    _STYLESHEETS = (('default.css', 'all'), ('layout.css', 'screen'), ('print.css', 'print'))
    """Static list of available style sheets used by the 'stylesheets()' method.

    The list consists of pairs (FILENAME, MEDIA), where FILENAME will be prefixed by the current
    URI of the 'Stylesheets' module and MEDIA corresponds to the 'lcg.Stylesheet' constructor
    argument of the same name.

    """
    _PREFERRED_LANGUAGE_COOKIE = 'wiking_preferred_language'
    
    def __init__(self, *args, **kwargs):
        super(Application, self).__init__(*args, **kwargs)
        self._reverse_mapping = dict([(v,k) for k,v in self._MAPPING.items()])

    def initialize(self, req):
        """Perform application specific initialization.

        This method is called once, just after Application instance creation.
        It is supposed to perform any application specific initialization

        Note, that 'req' is the first request that triggers initialization of
        the application, but the application will live much longer and serve a
        number of other requests which follow.  But this method is called only
        once for the first request.

        The default implementation does nothing.

        """
        pass
        
    def handle(self, req):
        """Handle the request.

        The Wiking Handler passes the request to the current application for
        further processing.  All errors and exceptions are handled by the
        handler.

        The return value may be one of three kinds:
        
           * 'wiking.Response' instance representing directly the HTTP response
             data and headers.
           * 'wiking.Document' instance, which is automatically converted to a
             'wiking.Response' by 'wiking.Handler' exporting the document into
             HTML through 'wiking.Exporter'.
           

        The method may also raise 'RequestError' exceptions to indicate special
        states or 'Redirect' exceptions to perform HTTP redirection.
             
        The default implementation uses static mapping of request paths (URI)
        to wiking modules defined by the class constant '\_MAPPING' to
        determine which module is responsible for processing the request and
        passes the request along to an instance of this module.  'NotFound' is
        raised if the mapping doesn't define an item for the current request
        URI.  You may re-implement this method if a different logic is more
        suitable for your application.

        """
        if not req.unresolved_path:
            # The request to the server's root URI is automatically redirected
            # to the first menu item's URI.  Redirection to hidden items is
            # avoided particularly because of default items added automatically
            # to the menu in CMS, such as _registration.  If the real menu is
            # empty, we don't want these items to be used for redirection.
            menu = [item for item in self.menu(req) if not item.hidden()]
            # The authentication must be performed before redirection, because
            # the current request may include login/logout commands which would
            # be discarded by the redirection.
            user = req.user()
            if menu:
                raise Redirect(menu[0].id())
            elif not user:
                # Here we handle the common case, that the menu is empty for
                # non-authenticated users and will be non-empty after the user
                # authenticates.  This presumption may not be theoretically
                # valid in all cases, but it typically works as expected.  If
                # the application doesn't want this behavior, it should not
                # return an empty menu.
                raise AuthenticationError()
            else:
                raise Forbidden()
        identifier = req.unresolved_path[0]
        try:
            modname = self._MAPPING[identifier]
        except KeyError:
            raise NotFound()
        mod = wiking.module(modname)
        assert isinstance(mod, RequestHandler)
        req.unresolved_path.pop(0)
        return req.forward(mod)
    
    def module_uri(self, req, modname):
        """Return the base URI of given Wiking module (relative to server root).

        The argument 'modname' is the Wiking module name as a string.

        If the module has no definite global path within the application, None may be returned.
        The exact behavior depends on the particular application in use.  Please see the
        documentation of this method in the relevant application class (such as
        'wiking.cms.Application.module_uri()' for applications built on Wiking CMS) for more
        details.

        The default implementation performs a reverse lookup in the '\_MAPPING' dictionary.  None
        is returned when there is no mapping item for the module, or when there is more than one
        item for the same module (which is also legal).

        This method should not be called directly by application code.  Use
        'wiking.Request.module_uri()' instead (which calls this method internally if necessary).
        
        """
        identitier = self._reverse_mapping.get(modname)
        return identitier and '/'+identitier or None

    def site_title(self, req):
        """Return site title as a string.

        This method returns the value of configuration option 'site_title' by default.  It may
        be overriden to change the title dynamically.
        
        """
        return wiking.cfg.site_title

    def site_subtitle(self, req):
        """Return site subtitle as a string or None.

        Site subtitle is normally appended to site title separated by a dash (if not 'None').  It
        is, however, exported in a differnt html element to allow independent styling.

        This method returns the value of configuration option 'site_subtitle' by default.  It may
        be overriden to change the subtitle dynamically.

        """
        return wiking.cfg.site_subtitle
    
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

    def contained_roles(self, req, role):
        """Return the sequence of user roles contained in given role.

        Arguments:
        
          req -- Current request as a 'Request' instance.
          role -- User role as a 'Role' instance.

        In general, user roles may be contained in each other.  This means that user's membersip in
        one role (let's say role A) may automatically imply his membership in other roles (B and C
        for example).  Roles B and C contain role A in this example.  If role containment
        is supported by the application, this method must be implemented and must return the list
        of all contained roles (including the given role itself and also transitively contained
        roles).

        In any case there may be no cycles in role containment, i.e. no role may contain itself,
        including transitive relations.  For instance, role A may not contain A; or if A contains B
        and B contains C then C may not contain A nor B nor C.

        
        """
        return ()
    
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
        """Return a list of all languages supported by the application.
        
        Returns a list of all supported languages as the corresponding alpha-2
        language codes.
        
        You should check, whether the translations for all the specified
        languages are available in the gettext catalog for Wiking and also for
        all the components you are using, such as LCG and Pytis.

        """
        return ['en']

    def preferred_languages(self, req):
        """Return a list of languages accepted by the current user in the order of their preference.

        The list of prefered languages allows wiking applications to serve
        multilingual content using the automatic Content Negotiation techique
        with a possibility for the user to switch between the available
        language variants manually.  You should never call this method directly
        in a Wiking application.  You rather want to call
        'Request.preferred_languages()'.

        You may need to override this method to change its logic completely or
        partially for given application if the default logic described below
        doesn't suit your needs.
        
        The default implementation uses a combination of user preferences set
        in 'Accept-Language' HTTP headers, explicit language switching and
        global defaults set in configuration.
        
        If the application supports language switching (the small widget at the
        top right corner in the default layout), the language selected there
        has the highest precedence (the selected value is saved in a cookie).
        The languages set through the HTTP header Accept-Language in browsers
        preferences immediately follow in the order of their precedence.  The
        last option (lowest precedence) is the default language configured for
        the server through 'default_language' and 'default_language_by_domain'
        configuration options.

        """
        if req.has_param('setlang'):
            # Use the language selected explicitly by the user in this request.
            selected = str(req.param('setlang'))
            req.set_param('setlang', None)
            req.set_cookie(self._PREFERRED_LANGUAGE_COOKIE, selected)
        else:
            # Use the language selected previously (if at all).
            selected = req.cookie(self._PREFERRED_LANGUAGE_COOKIE)
            if selected:
                selected = str(selected)
        if selected:
            languages = [selected]
        else:
            languages = []
        languages.extend([lang for lang in req.accepted_languages() if lang != selected])
        default = wiking.cfg.default_language_by_domain.get(req.server_hostname(),
                                                            wiking.cfg.default_language)
        if default and default not in languages:
            languages.append(default)
        return languages

    def stylesheets(self, req):
        """Return the list of all available style sheets as 'lcg.Stylesheet' instances.

        The application is responsible for handling the stylesheets (by their URIs) correctly.
        Wiking provides a generic 'Stylesheets' module for this purpose.

        The default implementation returns the list of style sheets defined by the '_STYLESHEETS'
        constant of the class (see its docstring for more info).

        """
        uri = req.module_uri('Stylesheets') or req.module_uri('Resources')
        if uri is not None:
            return [lcg.Stylesheet(file, uri=uri+'/'+file, media=media)
                    for file, media in self._STYLESHEETS]
        else:
            return []

    def registration_uri(self, req):
        """Return the URI for new user registration or None if registration is not allowed."""
        return None

    def password_reminder_uri(self, req):
        """Return the forgotten password link URI or None if password reminder not implemented."""
        return None

    def password_change_uri(self, req):
        """Return the change password URI or None if the link should not appear in login panel."""
        return None

    def login_is_email(self, req):
        """Return True iff e-mail addresses are used as login names.

        Using e-mail addresses as login names is quite typical.  If this is
        indicated by returning True from this method, the user interface will
        use more appropriate labels for login controls to avoid user's
        confusion.

        """
        return False

    def top_content(self, req):
        """Return the content displayed in the top portion of every page under the site title.
        
        Any content acceptable by 'lcg.coerce()' may be returned ('lcg.Content'
        instance, basestring, or their sequence).

        """
        return None

    def login_panel_content(self, req):
        """Return the extra content displayed in login panel below login controls.

        Any content acceptable by 'lcg.coerce()' may be returned.

        """
        return None
    
    def login_dialog_content(self, req):
        """Return the content displayed below the login dialog as 'lcg.Content' element(s).

        Any content acceptable by 'lcg.coerce()' may be returned.

        """
        return None
        
    def _powered_by_wiking(self, req):
        import wiking
        # Translators: Website idiom. This is followed by information on the underlying software
        # tools.  Means: This website runs on [...this and that software...].
        return (_("Powered by"), ' ',
                lcg.link('http://www.freebsoft.org/wiking', 'Wiking'), ' ', wiking.__version__)
    
    def _accessibility_statement_link(self, req):
        """Return lcg.Content containing a link to the Wiking Accessibility Statement or None.

        None is returned when the Documentation module (which normally serves
        the accessibility statement text) is not available (not mapped to a
        valid URI by the application).

        """
        doc = req.module_uri('Documentation')
        if doc:
            uri = doc + '/wiking/user/accessibility'
            class A11yStatementLink(lcg.Content):
                # A11y statement link with a hotkey (not supported by generic lcg links).
                def export(self, context):
                    g = context.generator()
                    return g.a(_("Accessibility Statement"), href=uri, accesskey='0')
            return A11yStatementLink()
        else:
            return None

    def menu_panel_title(self, req):
        """Return the displayed title of the left side hierarchical menu as a basestring.

        Python string, unicode or lcg.Translatable instance is accepted.

        """
        # Translators: Heading of webpage left side hierarchical navigation
        # menu containing a list of links to pages in this web section
        return _("In this section:")
    
    def menu_panel_tooltip(self, req):
        """Return the tooltip of the left side hierarchical menu as a basestring.


        Python string, unicode or lcg.Translatable instance is accepted.

        """
        return _("Local navigation")
        
    def menu_panel_bottom_content(self, req):
        """Return the additional content to be displayed in the hierarchical menu panel.

        Any content acceptable by 'lcg.coerce()' may be returned.  The content
        will be placed under the actual hierarchical menu list (at the bottom of the panel).

        """
        return None
    
    def right_panels_bottom_content(self, req):
        """Return the additional content to be displayed under right side panels.

        Any content acceptable by 'lcg.coerce()' may be returned.  The content
        will be placed under the list of panels on the right side (if panels
        are not hidden).

        """
        return None
    
    def bottom_bar_left_content(self, req):
        """Return the content displayed on the left side of the bottom bar above the page footer.

        Any content acceptable by 'lcg.coerce()' may be returned.

        """
        return self._powered_by_wiking(req)

    def bottom_bar_right_content(self, req):
        """Return the content displayed on the right side of the bottom bar above the page footer.

        Any content acceptable by 'lcg.coerce()' may be returned.

        """
        return self._accessibility_statement_link(req)

    def footer_content(self, req):
        """Return the content displayed in page footer as 'lcg.Content' element(s).
        
        Any content acceptable by 'lcg.coerce()' may be returned.

        """
        return lcg.p(_("Contact:"), ' ',
                     lcg.link("mailto:"+wiking.cfg.webmaster_address, wiking.cfg.webmaster_address))
    
    def _request_info(self, req):
        return dict(
            server_hostname=req.server_hostname(),
            uri=req.uri(),
            abs_uri=req.server_uri(current=True) + req.uri(),
            user=(req.user() and req.user().login() or 'anonymous'),
            remote_host=req.remote_host(),
            referer=req.header('Referer'),
            user_agent=req.header('User-Agent'),
            server_software='Wiking %s, LCG %s, Pytis %s' % \
                (wiking.__version__, lcg.__version__, pytis.__version__),
            )
    
    def log_error(self, req, error):
        """Write information about given RequestError instance into server's log.
        
        Log format is given by the 'log_format' configuration option.  Also, if
        'debug' configuration option is set, the log entry will contain basic
        traceback information (file names and line numbers).

        """
        variables = dict(self._request_info(req),
                         error_type=error.__class__.__name__)
        message = wiking.cfg.log_format % variables
        if wiking.cfg.debug:
            frames = ['%s:%d:%s()' % tuple(frame[1:4]) for frame in error.stack()]
            message += " (%s)" % ", ".join(reversed(frames))
        if isinstance(error, InternalServerError):
            message += ' ' + error.buginfo()
        log(OPR, message)

    def send_bug_report(self, req, einfo):
        """Send bug report by email if 'bug_report_address' is configured.

        If the configuration option 'bug_report_address' is set, information
        about the given exception (as returned by 'sys.exc_info()') is sent to
        the configured email address.

        """
        address = wiking.cfg.bug_report_address
        if address is None:
            return
        from xml.sax import saxutils
        import cgitb, traceback
        def param_value(param):
            if param in ('passwd', 'password'):
                value = '<password hidden>'
            else:
                value = req.param(param)
            if not isinstance(value, basestring):
                value = str(value)
            lines = value.splitlines()
            if len(lines) > 1:
                value = lines[0][:40] + '... (trimmed; total %d lines)' % len(lines)
            elif len(value) > 40:
                value = value[:40] + '... (trimmed; total %d chars)' % len(value)
            return saxutils.escape(value)
        def format_info(label, value):
            if value and (value.startswith('http://') or value.startswith('https://')):
                value = '<a href="%s">%s</a>' % (value, value)
            return "%s: %s\n" % (label, value)
        req_info_values = self._request_info(req)
        req_info = (
            ("URI", req_info_values['abs_uri']),
            ("Remote host", req_info_values['remote_host']),
            ("Remote user", req_info_values['user']),
            ("HTTP referer", req_info_values['referer']),
            ("User agent", req_info_values['user_agent']),
            ('Server software', req_info_values['server_software']),
            ("Request parameters", "\n"+
             "\n".join(["  %s = %s" % (saxutils.escape(param), param_value(param))
                        for param in req.params()])),
            )
        def escape(text):
            if isinstance(text, (tuple, list,)):
                return [escape(t) for t in text]
            else:
                return re.sub(r'[^\x01-\x7F]', '?', text)
        try:
            text = ("\n".join(["%s: %s" % pair for pair in req_info]) + "\n\n" +
                    cgitb.text(einfo))
        except UnicodeDecodeError:
            text = ("\n".join(["%s: %s" % (label, escape(value),) for label, value in req_info]) + "\n\n" +
                    escape(cgitb.text(einfo)))
        try:
            html = ("<html><pre>" +
                    "".join([format_info(label, value) for label, value in req_info]) +"\n\n"+
                    "".join(traceback.format_exception(*einfo)) +
                    "</pre>"+
                    cgitb.html(einfo) +"</html>")
        except UnicodeDecodeError:
            html = ("<html><pre>" +
                    "".join([format_info(label, escape(value)) for label, value in req_info]) +"\n\n"+
                    "".join(escape(traceback.format_exception(*einfo))) +
                    "</pre>"+
                    escape(cgitb.html(einfo))
                    +"</html>")
        subject = 'Wiking Error: ' + InternalServerError(einfo).buginfo()
        err = send_mail(address, subject, text, html=html,
                        headers=(('Reply-To', address),
                                 ('X-Wiking-Bug-Report-From', wiking.cfg.server_hostname)))
        if err:
            log(OPR, "Failed sending exception info to %s:" % address, err)
        else:
            log(OPR, "Traceback sent to %s." % address)
