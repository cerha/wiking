# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2017 OUI Technology Ltd.
# Copyright (C) 2019-2021, 2024 Tomáš Cerha <t.cerha@gmail.com>
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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Definition of default Wiking application and its API."""

import re
import os
import sys
import pytis
import wiking
import datetime
from xml.sax import saxutils

import lcg
from wiking import OPR, log

_ = lcg.TranslatableTextFactory('wiking')


class Application(wiking.Module):
    """Define Wiking application behavior.

    Wiking application is itself a Wiking module.  This module defines the
    basic application behavior.  You may customize your application by
    overriding this module and implementing the methods which form the
    Application API by your own means.

    """

    _MAPPING = {'_doc': 'Documentation',
                '_resources': 'Resources',
                'favicon.ico': 'SiteIcon',
                'robots.txt': 'Robots',
                }
    """Defines static assignment of modules responsible for handling distinct URI paths.

    The value is a dictionary, where keys are uri's and values are the names of
    the responsible modules as strings.  Only the first part of the request uri
    is used to determine the module.  Other parts (after the first slash) may
    be used by the module for further resolution of the request.

    This constant is used by the default implementation of
    'Application.handle()' and 'Application.module_uri()'.  See their
    documentation for more information.

    """

    _PREFERRED_LANGUAGE_COOKIE = 'wiking_preferred_language'

    def __init__(self, *args, **kwargs):
        super(Application, self).__init__(*args, **kwargs)
        self._mapping = dict(self._MAPPING)
        self._reverse_mapping = dict([(v, k) for k, v in self._MAPPING.items()])
        uri = self._reverse_mapping.get('Resources')
        if wiking.cfg.resources_version is not None and uri is not None:
            del self._mapping[uri]
            uri += '-' + wiking.cfg.resources_version
            self._mapping[uri] = 'Resources'
            self._reverse_mapping['Resources'] = uri

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

        The return value and possible exceptions is the same as described in
        'RequestHandler.handle()'.

        The default implementation uses static mapping of request paths (URI)
        to wiking modules defined by the class constant '_MAPPING' to
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
                raise wiking.Redirect(menu[0].id())
            elif not user:
                # Here we handle the common case, that the menu is empty for
                # non-authenticated users and will be non-empty after the user
                # authenticates.  This presumption may not be theoretically
                # valid in all cases, but it typically works as expected.  If
                # the application doesn't want this behavior, it should not
                # return an empty menu.
                raise wiking.AuthenticationError()
            else:
                raise wiking.Forbidden()
        identifier = req.unresolved_path[0]
        try:
            modname = self._mapping[identifier]
        except KeyError:
            raise wiking.NotFound()
        mod = wiking.module(modname)
        assert isinstance(mod, wiking.RequestHandler)
        req.unresolved_path.pop(0)
        return req.forward(mod)

    def module_uri(self, req, modname):
        """Return the base URI of given Wiking module (relative to server root).

        The argument 'modname' is the Wiking module name as a string.

        If the module has no definite global path within the application, None
        may be returned.  The exact behavior depends on the particular
        application in use.  Please see the documentation of this method in the
        relevant application class (such as
        'wiking.cms.Application.module_uri()' for applications built on Wiking
        CMS) for more details.

        The default implementation performs a reverse lookup in the '_MAPPING'
        dictionary.  None is returned when there is no mapping item for the
        module, or when there is more than one item for the same module (which
        is also legal).

        This method should not be called directly by application code.  Use
        'wiking.Request.module_uri()' instead (which calls this method
        internally if necessary).

        """
        identitier = self._reverse_mapping.get(modname)
        return identitier and '/' + identitier or None

    def authenticate(self, req, login, password, auth_type):
        """Return 'User' instance if given authentication credentials are valid.

        Arguments:
          req -- current request object
          login -- user's login name as a string
          password -- user supplied password as a string
          auth_type -- Short string describing the authentication method.  Each
            'wiking.AuthenticationProvider' subclass uses its specific string,
            such as "Cookie" for 'wiking.CookieAuthenticationProvider' etc.
            Only informational (for logging etc.).

        Returns a 'User' instance corresponding to given login name and
        password if the password is valid for given user or None if not.

        This method must be implemented by derived applications.  The default
        implementation always returns None.

        """
        return None

    def login_hook(self, req, user):
        """Hook executed after succesfull authentication.

        Arguments:

          req -- current request object
          user -- 'User' instance of the authenticated user

        The default implementation does nothing.  Derived applications may
        override it.

        """
        pass

    def logout_hook(self, req, user):
        """Hook executed when session is closed explicitly by user.

        Arguments:

          req -- current request object
          user -- 'User' instance of the authenticated user

        The default implementation does nothing.  Derived applications may
        override it.

        """
        pass

    def contained_roles(self, role):
        """Return the sequence of user roles contained in given role.

        Arguments:

          role -- User role as a 'Role' instance.

        In general, user roles may be contained in each other.  This means that
        user's membersip in one role (let's say role A) may automatically imply
        his membership in other roles (B and C for example).  Roles B and C
        contain role A in this example.  If role containment is supported by
        the application, this method must be implemented and must return the
        list of all contained roles (including the given role itself and also
        transitively contained roles).

        In any case there may be no cycles in role containment, i.e. no role
        may contain itself, including transitive relations.  For instance, role
        A may not contain A; or if A contains B and B contains C then C may not
        contain A nor B nor C.

        """
        return ()

    def site_title(self, req):
        """Return site title as a string.

        This method returns the value of configuration option 'site_title' by
        default.  It may be overriden to change the title dynamically.

        """
        return wiking.cfg.site_title

    def site_subtitle(self, req):
        """Return site subtitle as a string or None.

        Site subtitle is normally appended to site title separated by a dash
        (if not 'None').  It is, however, exported in a differnt html element
        to allow independent styling.

        This method returns the value of configuration option 'site_subtitle'
        by default.  It may be overriden to change the subtitle dynamically.

        """
        return wiking.cfg.site_subtitle

    def top_content(self, req):
        """Return the content displayed on the left side of the top bar.

        The returned value is a list of 'lcg.Content' instances or any other
        value acceptable by lcg.coerce()

        The content must behave nicely with the controls displayed on the right
        side of the top bar (see 'top_controls()').  This particularly means to
        to style the content to be responsive to the actual display size
        through CSS.  Otherwise the top bar may not fit to the visible area
        (hiding the controls at the right edge).

        The default implementation returns a list with just one element -- the
        'lcg.HtmlContent' instance displaying the site title and subtitle as
        returned by the methods 'site_title()' and 'site_subtitle()'.

        """
        def site_title(context, element, title, subtitle):
            g = context.generator()
            content = g.strong(title, cls='title')
            if subtitle:
                content += (g.strong(g.noescape(' &ndash; '), cls='separator') +
                            g.strong(subtitle, cls='subtitle'))
            return g.div(g.a(content, href='/'), id='site-title')
        return [lcg.HtmlContent(site_title, self.site_title(req), self.site_subtitle(req))]

    def top_controls(self, req):
        """Return the controls displayed on the right side of the top bar.

        The top bar displays the content returned by 'top_content()' (which
        normally is site title and subtitle) on the left and controls on the
        right.  Controls are simple (usually interactive) widgets for
        performing site global actions, such as logging in/out or switching
        languages (these two controls are returned by default).  Derived
        applications may override this method to add custom controls, customize
        the built-in controls or re-arrange the order of controls on the top
        bar.

        Make sure the controls don't take too much space or make them
        responsive to the actual display size through CSS.

        Any content acceptable by 'lcg.coerce()' may be returned ('lcg.Content'
        instance, str, or their sequence).  Consider using the base
        class 'wiking.TopBarControl' for definition of custom controls.

        The default implementation returns a list of two instances:
        'wiking.LoginControl' and 'wiking.LanguageSelection'.

        """
        return [wiking.LoginControl(), wiking.LanguageSelection(), wiking.MaximizedModeControl()]

    def menu(self, req):
        """Return the main navigation menu hierarchy.

        Arguments:

          req -- the current request object.

        Returns a sequence of 'MenuItem' instances representing the main menu
        hierarchy.

        The menu structure should usually remains unchanged throughout the
        application or at least throughout its major states, but this is just a
        common practice, not a requirement.  The application may decide to
        return a different menu for each request.

        """
        return ()

    def panels(self, req, lang):
        """Return a list of 'Panel' instances representing panels displayed on the page.

        The set of panels will usually be constant throughout the application,
        but this is just a common practice, not a requirement.  The application
        may decide to return a different set of panels for each request.

        See the Navigation section of the Wiking User's documentation for
        general information about panels.

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
        """Return a list of languages accepted by the user in the order of their preference.

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
        elif req.has_param('fb_locale'):
            # This parameter is used by Facebook's link sharing robot, which
            # explores the linked page when it is shared to determine what to
            # show on the page.
            selected = str(req.param('fb_locale').split('_')[0])
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

        The application is responsible for handling the returned stylesheets
        (serving them to clients).  Wiking provides a generic 'Resources'
        module for this purpose.

        The default implementation returns the 'default.css' stylesheet defined
        by Wiking.

        """
        return [lcg.Stylesheet('default.css')]

    def registration_uri(self, req):
        """Return the URI for new user registration or None if registration is not allowed."""
        return None

    def forgotten_password_uri(self, req):
        """Return the forgotten password link URI or None if password reset is not implemented."""
        return None

    def password_change_uri(self, req):
        """Return the change password URI or None if the link should not appear in login control."""
        return None

    def login_is_email(self, req):
        """Return True iff e-mail addresses are used as login names.

        Using e-mail addresses as login names is quite typical.  If this is
        indicated by returning True from this method, the user interface will
        use more appropriate labels for login controls to avoid user's
        confusion.

        """
        return False

    def body_class_names(self, req):
        """Return a sequence of CSS class names to assign to the BODY element.

        This allows application specific class names to be assigned to the top
        level BODY element in the HTML export of all pages.

        """
        return ()

    def login_dialog_top_content(self, req):
        """Return the content displayed above the login dialog as 'lcg.Content' element(s).

        Any content acceptable by 'lcg.coerce()' may be returned.

        """
        return None

    def login_dialog_bottom_content(self, req):
        """Return the content displayed below the login dialog as 'lcg.Content' element(s).

        Any content acceptable by 'lcg.coerce()' may be returned.

        """
        return self.login_dialog_content(req)

    def login_dialog_content(self, req):
        """Deprecated.  Use 'login_dialog_bottom_content()'."""
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
        doc_uri = req.module_uri('Documentation')
        if doc_uri:
            uri = doc_uri + '/wiking/user/accessibility'
            return lcg.HtmlContent(lambda context, element: context.generator().a(
                # accesskey not supported by generic lcg links.
                _("Accessibility Statement"), href=uri, accesskey='0',
            ))
        else:
            return None

    def menu_panel_title(self, req):
        """Return the displayed title of the left side hierarchical menu as a string."""
        # Translators: Heading of webpage left side hierarchical navigation
        # menu containing a list of links to pages in this web section
        return _("In this section:")

    def menu_panel_tooltip(self, req):
        """Return the tooltip of the left side hierarchical menu as a string."""
        return _("Local navigation")

    def menu_panel_bottom_content(self, req):
        """Return the additional content to be displayed in the hierarchical menu panel.

        Any content acceptable by 'lcg.coerce()' may be returned.  The content
        will be placed under the actual hierarchical menu list (at the bottom
        of the panel).

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
        return lcg.join((lcg.link('/privacy-policy', _("Privacy policy")),
                         self._accessibility_statement_link(req)), separator=' \u2022 ')

    def footer_content(self, req):
        """Return the content displayed in page footer as 'lcg.Content' element(s).

        Any content acceptable by 'lcg.coerce()' may be returned.

        """
        return lcg.p(_("Contact:"), ' ',
                     lcg.link("mailto:" + wiking.cfg.webmaster_address,
                              wiking.cfg.webmaster_address))

    def _send_bug_report(self, req, error, info, address):
        """Send traceback of given InternalServerError to given e-mail address."""
        def format_param(param):
            if param in ('passwd', 'password', 'initial_password'):
                value = '<password hidden>'
            else:
                try:
                    value = req.param(param)
                except UnicodeDecodeError as e:
                    # TODO: WsgiRequest.param() currently fails on invalid characters
                    # Once the problem is handled there, this may not be necessary.
                    value = "<UnicodeDecodeError: %s>" % e
                else:
                    if isinstance(value, wiking.FileUpload):
                        value = '%s; mime_type="%s"' % (value.filename(), value.mime_type())
                    elif isinstance(value, tuple):
                        value = repr(value)
                    else:
                        lines = value.splitlines()
                        if len(lines) > 1:
                            value = lines[0][:40] + '... (trimmed; total %d lines)' % len(lines)
                    if len(value) > 40:
                        value = value[:40] + '... (trimmed; total %d chars)' % len(value)
            return "   %s = %s" % (saxutils.escape(param), saxutils.escape(value))
        def maybe_link(value):
            if value and (value.startswith('http://') or value.startswith('https://')):
                value = '<a href="%s">%s</a>' % (value, value)
            return value
        header = (
            ("URI", info['abs_uri']),
            ("HTTP referer", info['referer']),
            ('Server software', info['server_software']),
            ('HTTP method', info['method']),
            ('Reference ID', info['ref_id']),
            ("Request parameters", "\n" + "\n".join(map(format_param, req.params()))),
        )
        text = "\n\n".join((
            "\n".join(["%s: %s" % pair for pair in header]),
            error.traceback(detailed=True, format='text'),
        ))
        html = "<html><pre>%s</pre>%s</html>" % (
            "\n".join(["%s: %s" % (label, maybe_link(value)) for label, value in header]),
            error.traceback(detailed=True, format='html'),
        )
        return wiking.send_mail(address, subject='Wiking Error: ' + error.signature(),
                                text=text, html=html,
                                headers=(('Reply-To', address),
                                         ('X-Wiking-Bug-Report-From',
                                          wiking.cfg.server_hostname)))

    def report_error(self, req, error):
        """Invoked for all errors to record their occurance for later review.

        This method is invoked for every 'ReqestError' exception raised within
        the application in order to record it and report the problem to the
        operator/maintainer/developer of the application.

        All errors are written into server's error log.  The amount of
        information and their format is controlled by the 'log_format'
        configuration option.

        Additionally, if the configuration option 'bug_report_address' is set,
        detailed cgitb traceback of the error is sent to the configured email
        address.

        Personal information, such as user's login, IP address or User Agent
        are intentionally not included in the e-mail but may be logged (if
        'log_format' contains them) and paired with the e-mailed traceback
        using the 'ref_id' value.

        For 'InternalServerError' a brief traceback (without the details from
        cgitb) is also written to the error log.  This allows jumping right to
        the code when the error log is observerd in an IDE during development.
        If 'debug' configuration option is set, the traceback is also logged
        for other error types for the same purpose.

        """
        if not isinstance(error, wiking.AuthenticationRedirect):
            info = dict(
                server_hostname=req.server_hostname(),
                uri=req.uri(),
                abs_uri=req.server_uri(current=True) + req.uri(),
                user=(req.user() and req.user().login() or 'anonymous'),
                remote_host=req.remote_host(),
                referer=req.header('Referer'),
                user_agent=req.header('User-Agent'),
                method=req.method(),
                server_software=('Wiking %s, LCG %s, Pytis %s' %
                                 (wiking.__version__, lcg.__version__, pytis.__version__)),
                error_type=error.__class__.__name__,
                ref_id=wiking.generate_random_string(10),
            )
            log(OPR, wiking.cfg.log_format % info)
            if isinstance(error, wiking.InternalServerError):
                log(OPR, error.traceback())
                address = wiking.cfg.bug_report_address
                if address:
                    err = self._send_bug_report(req, error, info, address)
                    if err:
                        log(OPR, "Failed sending error details to %s:" % address, err)
                    else:
                        log(OPR, "Error details sent to %s." % address)
            elif wiking.cfg.debug:
                log(OPR, error.traceback())
