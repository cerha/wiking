# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2017 OUI Technology Ltd.
# Copyright (C) 2019-2024 Tomáš Cerha <t.cerha@gmail.com>
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

import collections
import datetime
import json
import mimetypes
import base64
import binascii
import os
import re
import sys
import time
import cgitb
import traceback
from xml.sax import saxutils

import pytis.data as pd
import pytis.presentation as pp
import pytis.util
import pytis.web
import lcg
import wiking
from pytis.data.dbapi import DBAPIData

import http.client

_ = lcg.TranslatableTextFactory('wiking')

DBG = pytis.util.DEBUG
EVT = pytis.util.EVENT
OPR = pytis.util.OPERATIONAL
log = pytis.util.StreamLogger(sys.stderr).log


class RequestError(Exception):
    """Base class for predefined error states within request handling.

    Classes derived from this class may represent an error in the application
    itself ('InternalServerError'), temporary state ('ServiceUnavailable'), an
    invalid client request ('BadRequest', 'AuthenticationError', 'Forbidden',
    'AuthorizationError', 'NotFound', 'NotAcceptable', ...) or indicate other
    special state ('Redirect', 'NotModified', ...).  They map to error states
    defined by the HTTP protocol
    (https://www.w3.org/Protocols/rfc2616/rfc2616-sec10.html).

    The Wiking handler is responsible for handling these errors approprietly.
    This usually means to output a page with title and body content as returned
    by the methods 'title()' and 'content()' and setting the HTTP response
    status code according to 'status_code()'.  The overall page layout,
    including navigation and other static page content is displayed as on any
    other page.  API requests (not produced by a user from a browser) will
    automatically obtain a machine readable representation of the error as a
    JSON data structure.

    The classes which indicate an error in the application are in addition
    logged and serious errors are also sent by e-mail notification (if
    configuration option 'bug_report_address' is set).

    This class is abstract.  The error code and error message must be defined
    by a derived class.  Some subclasses may also require certain constructor
    arguments when the error is raised.

    """

    _STATUS_CODE = None
    """Relevant HTTP status code."""

    _TITLE = None
    """User visible error page title."""
    # TODO: Maybe the 'req' instance should be required as constructor argument
    # and avoided in all public methods.  This change requires changes in
    # applications, so it must be done carefully...

    def __init__(self, message=None):
        self._message = message
        self._traceback = ''.join(["Traceback (most recent call last):\n"] +
                                  traceback.format_stack()[:-1])
        super(RequestError, self).__init__()

    def _messages(self, req):
        """Return the error information as a tuple of (localizable) strings.

        Override this method to define the information returned by 'content()'
        and 'data()' at one place.

        """
        return (self._message,) if self._message else ()

    def status_code(self):
        """Return the HTTP response status code corresponding to the error type."""
        return self._STATUS_CODE

    def headers(self, req):
        """Return a list of (HEADER, VALUE) pairs to be set for this error response."""
        return []

    def title(self):
        """Return the error title as a (localizable) string."""
        return self._TITLE

    def content(self, req):
        """Return the error page content as a list of 'lcg.Content' instances.

        This content is displayed to users in a browser.  The displayed
        information should match the information returned by 'data()' but
        formatted for visual user agent.  It may also contain additional
        information specific for browser users.

        The default implementation returns the result of '_messages()'
        formatted as separate paragraphs.  It is recommended to override
        '_messages()' in derived classes to define the information for
        'content()' and 'data()' at one place.

        """
        return [lcg.p(message) for message in self._messages(req)]

    def data(self, req):
        """Return machine readable error representation as a dictionary.

        This representation is returned in API request responses.  The
        information should match the information returned by 'content()', but
        formatted as a dictionary of serializable values.

        The base class returns a dictionary with keys:
          type -- exception class name
          title -- result of 'title()'
          message -- result of '_messages()' concatenated into one string
            by spaces.

        It is recommended to override '_messages()' in derived classes to
        define the information for 'content()' and 'data()' at one place.

        This method may be overriden in derived classes to add additional
        values specific for a particular error type.

        """
        return dict(
            title=req.localize(self.title()),
            type=self.__class__.__name__,
            message=req.localize(lcg.concat(self._messages(req), separator=' ') or None),
        )

    def traceback(self):
        """Return the Python call stack trace saved in the constructor.

        This makes it possible to display the stack trace later for debugging
        purposes.  The returned value is a muliline string formatted similarly
        as ordinary Python exception traceback.

        """
        return self._traceback


class Redirect(RequestError):
    """Perform an HTTP redirection to given URI.

    Raising an exception of this class at any point of Wiking request
    processing will lead to HTTP redirection to the URI given to the exception
    instance constructor.  Wiking handler will automatically send the correct
    redirection response to the client (setting the appropriate HTTP headers
    and return codes).

    This class results in temporary redirection.  See 'PermanentRedirect' if
    you need a permanent redirection.

    """
    _STATUS_CODE = http.client.FOUND  # 302

    def __init__(self, uri, *args, **kwargs):
        """Arguments:

          uri -- redirection target URI as a string.  May be relative to the
            current request server address or absolute (beginning with
            'http://' or 'https://').  Relative URI is automatically prepended
            by the current request server address (the HTTP specification
            requires absolute URIs).  The URI can not contain any encoded query
            arguments or anchor.  If needed, they must be passed separately as
            additional positional or keyword arguments (see below).
          args, kwargs -- query arguments (and/or anchor) to be encoded into
            the final uri.  The same rules as for the arguments of
            'Request.make_uri()' apply.

        """
        assert isinstance(uri, str)
        super(Redirect, self).__init__()
        self._uri = uri
        self._args = args + tuple(kwargs.items())

    def uri(self):
        """Return the redirection target URI."""
        return self._uri

    def args(self):
        """Return the tuple of query arguments to be encoded to the URI.

        The arguments are returned in the form expected by 'Request.make_uri()'.

        """
        return self._args


class PermanentRedirect(Redirect):
    """Perform a permanent HTTP redirection to given URI.

    Same as the parent class, but results in permanent redirection according to
    HTTP specification.

    """
    _STATUS_CODE = http.client.MOVED_PERMANENTLY  # 301


class NotModified(RequestError):
    """Exception indicating that the requested has not been changed on server.

    Use when the current version of the resource is not newer than the version
    cached by the client.  Usually based on 'If-Modified-Since' headers or
    similar negotiation mechanism.

    """
    _STATUS_CODE = http.client.NOT_MODIFIED  # 304


class BadRequest(RequestError):
    """Error indicating invalid request argument values or their combination.

    Wiking applications usually ignore request arguments which they don't
    recognize.  This error is mostly usefull in situations, where the required
    arguments are missing or contain invalid values or their combinations.

    More precise error description may be optionally passed as constructor
    argument.  This message will be printed into user's browser window.  If
    no argument is passed, the default message `Invalid request arguments.'
    is printed.  If more arguments are passed, each message is printed as a
    separate paragraph.

    """
    _STATUS_CODE = http.client.BAD_REQUEST  # 400
    # Translators: An error page title
    _TITLE = _("Invalid Request")

    def _messages(self, req):
        return (self._message or _("Invalid request arguments."),
                _("Please, contact the administrator if you got this "
                  "response after a legitimate action."))


class AuthenticationError(RequestError):
    """Error indicating that authentication is required for the resource."""

    _STATUS_CODE = http.client.UNAUTHORIZED  # 401
    # Translators: This is a warning on a webpage which is only accessible for logged in users
    _TITLE = _("Authentication required")

    _HTTP_AUTH_MATCHER = re.compile('.*(Thunderbird|Icedove|Liferea|Pytis|unknown)/.*')
    """Regular expression matching user agents for which HTTP authentication is used automatically.

    HTTP authentication may be explicitly requested by the client through a
    special request argument '__http_auth'.  But sometimes it is more practical
    to avoid such argument in the URL.  For example we want to publish a URL of
    an RSS channel.  Some RSS readers do support cookie based authentication
    and we don't want to force them to use HTTP authentication for its lack of
    logout possibility and other drawbacks.  However, other RSS readers don't
    support cookie based authentication and we don't want to publish two
    distinct URLs and explain which to choose in which case.  Thus we are a
    little brave and guess the appropriate authentication method from the User
    Agent header.

    The currently recognized user agents are Thunderbird mail reader (for its
    built in RSS support) and Liferea.

    """

    def headers(self, req):
        if ((wiking.cfg.allow_http_authentication
             and (req.param('__http_auth')  # HTTP Basic auth explicitly requested.
                  # Force Basic auth for certain clients.
                  or self._HTTP_AUTH_MATCHER.match(req.header('User-Agent', 'unknown/?'))
                  # This was an invalid Basic auth attempt.
                  or req.header('Authorization', '').startswith('Basic ')))):
            auth_type = 'Basic'
        else:
            # This is not a stantdard HTTP authentication type, but it is recommended by some.
            auth_type = 'Cookie'
        return [('WWW-Authenticate', '%s realm="%s"' % (auth_type, wiking.cfg.site_title))]

    def content(self, req):
        if self._message:
            req.message(self._message, req.ERROR)
        appl = wiking.module.Application
        return LoginDialog(registration_uri=appl.registration_uri(req),
                           forgotten_password_uri=appl.forgotten_password_uri(req),
                           top_content=appl.login_dialog_top_content(req),
                           bottom_content=appl.login_dialog_bottom_content(req),
                           login_is_email=appl.login_is_email(req))


class AuthenticationRedirect(AuthenticationError):
    """Has the same effect as AuthenticationError, but is just not an error."""

    # Translators: Login dialog page title (use a noun).
    _TITLE = _("Login")


class Forbidden(RequestError):
    """Error indicating unavailable request target.

    This is a more generic case of denied access.  Use 'AuthorizationError' if
    the access to the target depends on authorization settings.  Use
    'Forbidden' when the target is globally unavailable, such as when directory
    listing is denied to everyone, but files in that directory may be
    accessible.

    """
    _STATUS_CODE = http.client.FORBIDDEN  # 403
    # Translators: An error page title
    _TITLE = _("Access Denied")

    def _messages(self, req):
        return (self._message or _("The item '%s' is not available.", req.uri()),
                _("The item exists on the server, but can not be accessed."))


class AuthorizationError(Forbidden):
    """Error indicating that the user doesn't have privilegs for the action.

    Use when the access to the target depends on authorization settings.
    Typically when the user could be granted additional privilegs to get access
    to the resource.  Use 'Forbidden' when the target is globally unavailable.

    You can pass custom error messages as constructor arguments (each argument
    will be formatted as a separate paragraph of text).  If no arguments are
    passed, a default generic message "You don't have sufficient privilegs for
    this action." is used.

    """

    def _messages(self, req):
        return (self._message or
                _("You don't have sufficient privileges for this action."),
                _("If you are sure that you are logged in under the right account "
                  "and you believe that this is a problem of access rights assignment, "
                  "please contact the administrator at %s.", wiking.cfg.webmaster_address))

    def content(self, req):
        message, notice = self._messages(req)
        return [lcg.p(message), lcg.p(req.translate(notice), formatted=True)]


class NotFound(RequestError):
    """Error indicating invalid request target."""
    _STATUS_CODE = http.client.NOT_FOUND  # 404
    # Translators: Error page title when requesting URI which does not exist on server.
    _TITLE = _("Item Not Found")

    def _messages(self, req):
        return (self._message or
                # Translators: The word 'item' is intentionaly very generic,
                # since it may mean a page, image, streaming video, RSS channel
                # or anything else.
                _("The item '%s' does not exist on this server or cannot be served.",
                  req.uri()),
                _("If you are sure the web address is correct, but are encountering "
                  "this error, please contact the administrator at %s.",
                  wiking.cfg.webmaster_address))

    def content(self, req):
        message, notice = self._messages(req)
        return [lcg.p(message), lcg.p(req.translate(notice), formatted=True)]


class NotAcceptable(RequestError):
    """Error indicating unavailability of the resource in the requested language."""
    _STATUS_CODE = http.client.NOT_ACCEPTABLE  # 406
    # Translators: Title of a dialog on a webpage
    _TITLE = _("Language selection")

    def __init__(self, message=None, variants=()):
        """Arguments:

          message -- as in the parent class
          variants -- sequence of language codes of available language variants
            of the requested resource (page/document/...).

        """
        super(NotAcceptable, self).__init__(message=message)
        self._variants = tuple(variants)

    def _messages(self, req):
        return (self._message or _("The resource '%s' is not available in either "
                                   "of the requested languages.", req.uri()),)

    def content(self, req):
        content = super(NotAcceptable, self).content(req)
        if self._variants:
            # Translators: Meaning language variants. A selection of links to various language
            # versions follows.
            content.extend((
                lcg.p(_("The available variants are:")),
                lcg.ul([lcg.link("%s?setlang=%s" % (req.uri(), l),
                                 label=lcg.language_name(l) or l)
                        for l in self._variants]),
            ))
        content.extend((
            lcg.HorizontalSeparator(),
            lcg.p(_("Your browser is configured to accept only the following languages:")),
            lcg.ul([lcg.language_name(l) or l for l in req.preferred_languages()]),
            lcg.p(_("If you want to accept other languages permanently, setup the language "
                    "preferences in your browser or contact your system administrator.")),
        ))
        return content

    def data(self, req):
        return dict(
            super(NotAcceptable, self).data(req),
            variants=self._variants,
        )


class InternalServerError(RequestError):
    """General error in application -- error message is required as an argument."""
    _STATUS_CODE = http.client.INTERNAL_SERVER_ERROR  # 500
    _TITLE = _("Internal Server Error")

    def __init__(self):
        cls, value, tb = sys.exc_info()
        try:
            self._exception_class = cls
            self._basic_traceback = ''.join(traceback.format_exception(cls, value, tb))
            try:
                # cgitb returns str with undocumented encoding (seems to be latin1).
                self._html_traceback = cgitb.html((cls, value, tb))
                self._text_traceback = cgitb.text((cls, value, tb))
            except Exception as e:
                # cgitb sometimes fails when the introspection touches
                # something sensitive, such as database objects.
                self._html_traceback = None
                self._text_traceback = None
                self._cgitb_exception = e
            while tb.tb_next is not None:
                tb = tb.tb_next
            self._filename = os.path.split(tb.tb_frame.f_code.co_filename)[-1]
            self._lineno = tb.tb_lineno
        finally:
            # See sys.exc_info() documentation why we are deleting it here.
            del tb
        super(InternalServerError, self).__init__()

    def traceback(self, detailed=False, format='text'):
        """Return the traceback of the exception which caused this InternalServerError.

        Arguments:

          detailed -- if false (by default) a brief textual traceback is
            returned as a mutiline string with formatting known from common
            Python tracebacks.  If true is passed, the traceback produced by
            'cgitb' will be returned, including relevant parameter and variable
            values.

          format -- traceback formatting; Use 'text' for plain text traceback
            (default) or 'html' for HTML formatted traceback.  Only relevant
            when 'detailed' is true.

        Note that in this class we don't care about the constructor call stack
        trace as in the parent class method.  For 'InternalServerError' we are
        interested in the traceback of the exception which was active in the
        time of the constructor call.

        """
        assert format in ('text', 'html') if detailed else ('text',)
        if not detailed:
            return self._basic_traceback
        elif format == 'html':
            return self._html_traceback or '<pre>' + self._basic_traceback + '</pre>'
        else:
            return self._text_traceback or self._basic_traceback

    def signature(self):
        """Return short info about the error type and its source code location."""
        return "%s at %s line %d" % (self._exception_class.__name__, self._filename, self._lineno)

    def content(self, req):
        # TODO: Even though the admin address is in a formatted paragraph, it
        # is not formatted as a link during internal server error export.  It
        # works well in all other cases.
        if not wiking.cfg.debug:
            return (lcg.p(_("The server was unable to complete your request "
                            "due to a technical problem.")),
                    lcg.p(lcg.strong(_("We apologize."))),
                    lcg.p(_("The issue has been recorded and we are working "
                            "towards fixing it.")),
                    lcg.p(req.translate(_("Contact the server administrator, "
                                          "%s if you need assistance.",
                                          wiking.cfg.webmaster_address)), formatted=True))
        elif not self._html_traceback:
            return (lcg.p("Traceback formatting using cgitb failed: %s" % self._cgitb_exception),
                    lcg.p("Plain text traceback follows:"),
                    lcg.pre(self.traceback()))
        else:
            return lcg.HtmlContent(self._html_traceback)


class ServiceUnavailable(RequestError):
    """Error indicating a temporary problem, which may not appaper in further requests."""
    _STATUS_CODE = http.client.SERVICE_UNAVAILABLE  # 503
    _TITLE = _("Service Unavailable")

    def _messages(self, req):
        return (self._message or
                _("The requested function is currently unavailable. "
                  "Try repeating your request later."),)

    def content(self, req):
        return (super(ServiceUnavailable, self).content(req) +
                [lcg.p(_("Please inform the server administrator, %s if the problem "
                         "persists.", wiking.cfg.webmaster_address), formatted=True)])


# ============================================================================
# NOTE: Abort is not a RequestError subclass!

class Abort(Exception):
    """Exception aborting regular request processing and returning arbitrary result.

    Raising this error interrupts regular request processing chain and forces
    given result as the result of top level request handler.  Raising this
    exception has the same effect as returning given result from
    'Application.handle()', but may be invoked from anywhere, even from places
    where you otherwise can not influence the final return value of the request
    handler.

    """

    def __init__(self, result):
        """Arguments:

        result -- request processing result as 'lcg.Content', 'wiking.Document'
          or 'wiking.Response' instance.

        """
        assert isinstance(result, (lcg.Content, wiking.Document, wiking.Response))
        self._result = result
        super(Abort, self).__init__()

    def result(self):
        """Return the request processing result passed to the constructor."""
        return self._result


# ============================================================================


class Theme:
    """Color theme representation.

    Color themes are used for substitution of symbolic color names by color
    values in stylesheets served by Wiking's 'Resources' module.

    The available colors are defined by 'Theme.COLORS' as a tuple of
    'Theme.Color' instances.

    """
    class Color:
        """Theme color specification.

        Each color defines its own identifier and optionally the identifier of
        another theme color, which provides the default value for this color if
        no explicit value is defined in the color 'Theme'.

        """

        def __init__(self, id, inherit=None):
            self._id = id
            self._inherit = inherit

        def id(self):
            return self._id

        def inherit(self):
            return self._inherit

    COLORS = (
        Color('foreground'),
        Color('background'),
        Color('highlight-bg'),
        Color('border'),
        Color('frame-fg', inherit='foreground'),
        Color('frame-bg', inherit='background'),
        Color('frame-border', inherit='border'),
        Color('heading-fg', inherit='foreground'),
        Color('heading-bg', inherit='background'),
        Color('heading-line', inherit='border'),
        Color('link'),
        Color('link-visited', inherit='link'),
        Color('link-hover', inherit='link'),
        Color('help', inherit='foreground'),
        Color('error-fg'),
        Color('error-bg'),
        Color('error-border'),
        Color('message-fg'),
        Color('message-bg'),
        Color('message-border'),
        Color('table-cell', inherit='background'),
        Color('table-cell2', inherit='table-cell'),
        Color('top-fg', inherit='foreground'),
        Color('top-bg', inherit='background'),
        Color('top-border', inherit='border'),
        Color('inactive-folder', inherit='heading-bg'),
        Color('meta-fg', inherit='foreground'),
        Color('meta-bg', inherit='background'),
    )

    _DEFAULTS = {'foreground': '#000',
                 'background': '#fff',
                 'border': '#cfdfef',
                 'heading-bg': '#dae6f6',
                 'heading-line': '#ddd',
                 'frame-bg': '#f0f0f0',
                 'frame-border': '#e4e4e4',
                 'link': '#16166e',
                 'link-hover': '#009',
                 'meta-fg': '#206573',
                 'meta-bg': 'transparent',
                 'help': '#444',
                 'error-bg': '#fdb',
                 'error-border': '#fba',
                 'message-bg': '#cfc',
                 'message-border': '#aea',
                 'table-cell': '#fafefe',
                 'table-cell2': '#f8fbfb',
                 'top-bg': '#e4e5e4;',
                 'top-border': '#ccdcec',
                 'highlight-bg': '#ff7c90',
                 'inactive-folder': '#e0e0e0',
                 }

    def __init__(self, colors=None):
        """Arguments:

           colors -- dictionary of theme colors.  Keys are string identifiers
             of theme colors from 'Theme.COLORS' and values are RGB string color
             representaions, such as "#0f0" or "#00ff00".

        """
        coldict = dict([(c.id(), c) for c in self.COLORS])

        def color(key):
            if colors and key in colors:
                return colors[key]
            elif key in self._DEFAULTS:
                return self._DEFAULTS[key]
            else:
                inherit = coldict[key].inherit()
                if inherit:
                    return color(inherit)
                else:
                    return 'inherit'
        self._theme = {'color': dict([(key, color(key)) for key in coldict])}

    def __getitem__(self, key):
        return self._theme[key]


class MenuItem:
    """Abstract menu item representation."""

    def __init__(self, id, title, descr=None, submenu=(), hidden=False, active=True,
                 foldable=False, order=None, variants=None):
        """Arguments:

          id -- unique menu item identifier (str) which is at the same
            time used as the target URI.  It should start with a slash (if not,
            it is prepended automatically, but this is deprecated).
          title -- title as a (translatable) string displayed in menu.
          descr -- brief description as a (translatable) string used as a
            tooltip or a sitemap description.
          submenu -- sequence of subordinate menu items as nested 'MenuItem'
            instances.
          hidden -- iff true, the item will not be present in the menu, but
          active -- iff false, the item will be presented as inactive.
            Designed to visually distinguish items disabled due to access
            rights or some other conditions.  It is left up to the application
            developer to decide whether to hide such items alltogether or
            present them as inactive.  The item will be presented as inactive
            (ie. grayed out), but in fact will remain active (clickable) to
            allow invocation of the target, which should lead to displaying a
            more descriptive error page explaining the reason.  It the
            responsibility of the application to handle the request properly.
          foldable -- iff true, the item's submenu will be presented as a
            foldable tree if the techology allows it (if the user agent
            supports JavaScript).
          order -- item order on its level of hierarchy as any python object
            supporting comparison.  If None, the items will be presented in the
            order in which they appear.
          variants -- sequence of language codes (strings) in which the item is
            available.  If None, the item is supposed to exist in all
            languages.  This allows to filter out only items available in the
            current user's language when the page is displayed.

        """
        self._id = id
        self._title = title
        self._descr = descr
        self._hidden = hidden
        self._active = active
        self._foldable = foldable
        self._submenu = sorted(submenu, key=lambda i: i.order() or 0)
        self._order = order
        self._variants = variants

    def id(self):
        return self._id

    def title(self):
        return self._title

    def descr(self):
        return self._descr

    def hidden(self):
        return self._hidden

    def active(self):
        return self._active

    def foldable(self):
        return self._foldable

    def order(self):
        return self._order

    def submenu(self):
        return self._submenu

    def variants(self):
        return self._variants


class Panel:
    """Panel representation to be passed to 'Document.build()'.

    Panels are small applet windows displayed by the right side of the page (in
    the default style).  They can hold arbitrary content defined by the
    application and optionally link to RSS channels.

    """

    def __init__(self, id, title, content, titlebar_content=None,
                 accessible_title=None, channel=None):
        """
        @type id: str
        @param id: Panel unique identifier.  This identifier is included in
        the output and thus may be used for panel specific styling.

        @type title: str
        @param title: Title displayed in panel heading.

        @type content: L{lcg.Content}
        @param content: Content displayed within the panel area.

        @type accessible_title: str
        @param accessible_title: Panel title for assistive technologies or
        None.  Panel is by default represented by its 'title' to assistive
        technologies.  If you need to use a more descriptive title for this
        purpose than it is desirable to display in panel heading, use this
        argument to pass an alternative title.

        @type titlebar_content: L{lcg.Content} @param titlebar_content:
        Additional panel title bar content.  If defined, the exported content
        will be appended to the panel title inside the panel title bar.

        @type channel: str
        @param channel: RSS channel URI if this panel represents an RSS
        channel.  If not None, the panel will indicate a channel icon with a
        link to the channel.  Channels of all panels present on a page will
        also be automatically included in <link> tags within the page header.

        """
        assert isinstance(id, str), id
        assert isinstance(title, str), title
        assert isinstance(content, lcg.Content), content
        assert accessible_title is None or isinstance(accessible_title, str), accessible_title
        assert channel is None or isinstance(channel, str), channel
        self._id = id
        self._title = title
        self._content = content
        self._accessible_title = accessible_title or title
        self._titlebar_content = titlebar_content
        self._channel = channel

    def id(self):
        return self._id

    def title(self):
        return self._title

    def accessible_title(self):
        return self._accessible_title

    def titlebar_content(self):
        return self._titlebar_content

    # TODO: navigable ....

    def content(self):
        return self._content

    def channel(self):
        return self._channel


class Document:
    """Independent Wiking document representation.

    The 'Document' is Wiking's abstraction of an LCG document (represented by
    'lcg.ContentNode').

    This allows us to initialize document data without actually creating the
    whole LCG node hierarchy and specifying all the required attributes at the
    same time.  Default attribute values sensible in the Wiking environment are
    substituted and the whole content node hierarchy is built afterwards by
    Wiking handler which is responsible to produce the HTTP response out of the
    'Document' instance by converting it to 'lcg.ContentNode' and exporting it
    to HTML.

    """

    def __init__(self, title, content, subtitle=None, lang=None, sec_lang=None,
                 variants=None, globals=None, layout=None):
        """Arguments:

          title -- document title as a (translatable) string.  Can be also
            None, in which case the title will default to the title of the
            corresponding menu item (if found).
          content -- document content as 'lcg.Content' instance or their
            sequence.  If a sequence is passed, it is allowed to contain None
            values, which will be omitted.
          subtitle -- document subtitle as a (translatable) string.  If not
            None, it will be appended to the title.
          lang -- language of the content as a corresponding iso language code.
            Can be None if the content is not language dependent -- i.e. is all
            composed of translatable text, so that it can be exported into any
            target language (supported by the application and its
            translations).  Should always be defined for language dependent
            content, unless the whole application is mono-lingual.
          sec_lang -- secondary language of the content as a an iso language
            code or None if no secondary language applies.  Corrensonds to the
            'lcg.Exporter.Context' constructor argument of the same name.
          variants -- available language variants as a sequence of language
            codes.  Should be defined if only a limited set of target languages
            for the document exist.  For example when the document is read form
            a file or a database and it is known which other versions of the
            source exist.  If None, variants default to the variants defined by
            the corresponding menu item (if found) or to application-wide set
            of all available languages.
          layout -- output layout as one of `wiking.Exporter.Layout' constants
            or None for the default layout.

        """
        self._title = title
        self._subtitle = subtitle
        self._content = content
        self._lang = lang
        self._sec_lang = sec_lang
        self._variants = variants
        self._globals = globals
        self._layout = layout

    def title(self):
        """Return the 'title' passed to the constructor."""
        return self._title

    def subtitle(self):
        """Return the 'subtitle' passed to the constructor."""
        return self._subtitle

    def content(self):
        """Return the 'content' passed to the constructor."""
        return self._content

    def lang(self):
        """Return the 'lang' passed to the constructor."""
        return self._lang

    def sec_lang(self):
        """Return the 'sec_lang' passed to the constructor."""
        return self._sec_lang

    def variants(self):
        """Return the 'variants' passed to the constructor."""
        return self._variants

    def globals(self):
        """Return the 'globals' passed to the constructor."""
        return self._globals

    def layout(self):
        """Return the 'layout' passed to the constructor."""
        return self._layout

    def clone(self, **kwargs):
        """Return an instance identical with this one, except for arguments passed to this method.

        Keyword arguments are the same as in the constructor.  Their values
        override the properties of the original instance (original constructor
        arguments).

        """
        args = [(k[1:], v) for k, v in self.__dict__.items() if k.startswith('_')]
        return self.__class__(**dict(args, **kwargs))


class Response:
    """Abstract representation of HTTP request response.

    The response is the final result of request processing.  Methods involved
    in request processing, such as Application.handle(),
    RequestHandler.handle() and ActionHandler.action_*(), may return either a
    'wiking.Document' instance (ordinary page further processed by
    'wiking.Exporter') or a 'wiking.Response' directly.  Using
    'wiking.Response' gives the application an unlimited freedom to return any
    possible content which may be transmitted over an HTTP channel.

    See also 'wiking.serve_file()' for a convenience function reading the
    response data out of a file within server's filesystem.

    """

    def __init__(self, data, content_type='text/html', content_length=None,
                 status_code=http.client.OK, last_modified=None, filename=None,
                 inline=False, headers=()):
        """Arguments:

          data -- respnse data as one of the types described below.

          content_type -- The value to be used for the 'Content-Type' HTTP
            header (str).  When 'data' is a string and 'content_type' is one of
            "text/html", "application/xml", "text/css" or "text/plain", the
            charset information is appended automatically to the value.  So for
            example "text/plain" will be converted to "text/plain;
            charset=UTF-8".

          content_length -- Explicit value for the 'Content-Length' HTTP header
            (str).  Set automatically when 'data' is 'str' or 'bytes', but
            should be supplied when 'data' is an iterable object.

          status_code -- integer number denoting the HTTP response status code
            (default is 'httplib.OK').  It is recommended to use 'httplib'
            constants for the status codes.

          filename -- file name (str) for the 'Content-disposition' HTTP
            header.  This has the same effect as adding a pair
            ('Content-disposition', "attachment; filename=<filename>" to
            'headers'.  The browser will usually show a "Save File" dialog and
            suggest given file name as the default name for saving the request
            result into a file.

          inline -- set to True to force the data to be displayed inline in the
            browser window when 'filename' is set.  Otherwise the content is
            downloaded and saved to users the filesystem.  The user can still
            save inline content using the "Save As" function of the browser.
            Actually modifies the 'Content-Disposition' header mentioned above
            by replacing 'attachment' by 'inline'.  Irrelevant when 'filename'
            not set.

          last_modified -- last modification time as a python datetime
            instance.  The value will be used for the 'Last-Modified' HTTP
            header (the appropriate date formatting is applied automatically).
            Also, if the given modification time is equal or older than the
            'If-Modified-Since' header passed by the client, the response is
            automatically replaced by the 403 Not modified HTTP response (see
            also 'Request.cached_since()').  If it may save some extra
            processing, you are still encouraged to raise the
            'wiking.NotModified' exception earlier but if not, you don't need
            to care and just pass 'last_modified' and let the handler decide
            for you.

          headers -- any additional HTTP headers to be sent with the request as
            a sequence of pairs NAME, VALUE (strings).

        The supported response data types:
          bytes -- is sent unchanged to the client
          str -- is encoded using the current request encoding
          iterable -- iterable object (typically a generator) returning
            response data in chunks.  The returned chunks must be strings or bytes.

        """
        self._data = data
        self._content_type = content_type
        self._content_length = content_length
        self._status_code = status_code
        self._last_modified = last_modified
        self._headers = headers
        self._filename = filename
        self._inline = inline

    def data(self):
        return self._data

    def content_type(self):
        return self._content_type

    def content_length(self):
        return self._content_length

    def status_code(self):
        return self._status_code

    def last_modified(self):
        return self._last_modified

    def filename(self):
        return self._filename

    def inline(self):
        return self._inline

    def headers(self):
        return tuple(self._headers)

    def add_header(self, name, value):
        if not isinstance(self._headers, list):
            self._headers = list(self._headers)
        self._headers.append((name, value))


class Channel:
    """RSS channel specification."""

    def __init__(self, id, title, descr, content, limit=None, sorting=None, condition=None,
                 webmaster=None):
        """
        @type id: str
        @param id: Channel identifier unique within one module's channels.  The
        identifier is used as a part of channel URL, so it should not contain
        special characters.

        @type title: str
        @param title: Channel title

        @type descr: str
        @param descr: Channel description/subtitle

        @type content: L{ChannelContent}
        @param content: Channel content data specification (defines the structure of items).

        @type limit: int
        @param limit: Maximum number of items present in the channel.

        @type sorting: tuple of pairs (COLUMN_ID, DIRECTION)
        @param sorting: Pytis data sorting specification.

        @type condition: L{pytis.data.Operator}
        @param condition: Pytis data condition filtering the items present in
        the channel (appended to any other conditions imposed by the underlying
        module).

        @type webmaster: str
        @param webmaster: Channel webmaster e-mail address.  If None,
        'wiking.cfg.webmaster_address' is used.

        """
        assert isinstance(id, str)
        assert isinstance(title, str)
        assert isinstance(descr, str)
        assert isinstance(content, ChannelContent)
        self._id = id
        self._title = title
        self._descr = descr
        self._content = content
        self._limit = limit
        self._sorting = sorting
        self._condition = condition
        self._webmaster = webmaster

    def id(self):
        return self._id

    def title(self):
        return self._title

    def descr(self):
        return self._descr

    def content(self):
        return self._content

    def limit(self):
        return self._limit

    def sorting(self):
        return self._sorting

    def condition(self):
        return self._condition

    def webmaster(self):
        return self._webmaster


class ChannelContent:
    """Defines how PytisModule records map to RSS channel items.

    Used for 'Channel' 'content' constructor argument.

    The constructor arguments correspond to the supported channel item fields
    and given values define how to get the field value from the module's
    record.  Each value is either string, function (callable object) or None.
    In case of a string, the field value is taken directly from the record's
    exported field value of the same name.  A callable object allows more
    flexibility.  Given function is called with two arguments ('req' and
    'record') and the returned value is used directly.  The function must
    return a string or None.  If the specification value is None or if the
    resulting field value is None, the field is not included in the output or a
    default value is used (as documented for each field).

    """

    def __init__(self, title, link=None, descr=None, date=None, author=None):
        """
        @type title: str or callable
        @param title: Item title field specification.

        @type link: str, callable or None
        @param link: Item link field specification.  If None, the default
        item link is determined automatically as the module's record URL.

        @type descr: str, callable or None
        @param descr: Item description field specification.

        @type date: str, callable or None
        @param date: Item date field specification.  The result must be
        'datetime.datetime' instance.  If column name is used, its type must be
        'pytis.data.DateTime'.  If function is used, it must return a
        'datetime.datetime' instance.

        @type author: str, callable or None
        @param author: Item author field specification.

        See the class docstring for common details about field
        specifications.

        """
        assert isinstance(title, str) or callable(title), title
        assert link is None or isinstance(link, str) or callable(link), link
        assert (descr is None or isinstance(descr, str) or callable(descr)), descr
        assert date is None or isinstance(date, str) or callable(date), date
        assert (author is None or isinstance(author, str) or callable(author)), author
        self._title = title
        self._link = link
        self._descr = descr
        self._date = date
        self._author = author

    def title(self):
        return self._title

    def link(self):
        return self._link

    def descr(self):
        return self._descr

    def date(self):
        return self._date

    def author(self):
        return self._author


class RssWriter:
    """Simple RSS stream writer."""

    def __init__(self, stream):
        self._stream = stream

    def _write_tag(self, tag, value, escape=True):
        if value is not None:
            if escape:
                value = saxutils.escape(value)
            data = '<%s>%s</%s>\n' % (tag, value, tag)
            self._stream.write(data.encode('utf-8'))

    def start(self, link, title, description, language=None, webmaster=None, generator=None,
              ttl=60):
        """Call exactly once to write channel meta data into the stream."""
        self._stream.write('<?xml version="1.0" encoding="UTF-8"?>\n' +
                           '<rss version="2.0">\n' +
                           '<channel>\n')
        self._write_tag('title', title)
        self._write_tag('link', link, escape=False)
        self._write_tag('description', description)
        self._write_tag('language', language)
        self._write_tag('webMaster', webmaster, escape=False)
        self._write_tag('generator', generator)
        self._write_tag('ttl', ttl, escape=False)

    def item(self, link, title, guid=None, description=None, pubdate=None, author=None):
        """Call repeatedly to write a single channel item."""
        if pubdate:
            pubdate = format_http_date(pubdate)
        self._stream.write('<item>\n')
        self._write_tag('title', title or '')
        self._write_tag('guid', guid or link or '', escape=False)
        self._write_tag('link', link or '', escape=False)
        self._write_tag('description', description)
        self._write_tag('pubDate', pubdate)
        self._write_tag('author', author)
        self._stream.write('</item>\n')

    def finish(self):
        """Call exactly once to write the final data into the stream."""
        self._stream.write('</channel>\n</rss>\n')


class PasswordStorage:
    """Abstract base class for various methods of transforming passwords for storage.

    Defines the API for conversion of user passwords before storing and
    checking user passwords against their stored representations.  Passwords are
    typically not stored in plain text but rather as their hashes to improve
    security.  The main purpose of this class is having a single API for
    various methods of such password transformations.  This class actually does
    not store the passwords anywhere, only transforms them for storage and
    verification.

    The derived class must implement the methods 'stored_password()' and
    'check_password()' according to their docstring.

    """

    def stored_password(self, password):
        """Return the transformed representation of given password for storing.

        Arguments:
          password -- the password to transform in clear text as a str.

        Returns the transformed representation of the password as a str.

        """
        raise NotImplementedError()

    def check_password(self, password, stored_password):
        """Verify that given password is the correct original of the stored password.

        Arguments:
          password -- the password to check in clear text as a str.
          stored_password -- the stored version of the correct password as a str.

        Returns True if the password is correct. False otherwise.

        """
        raise NotImplementedError()

    def _equals(self, string1, string2):
        """Compare two strings in length-constant time.

        Comparison using the Python == operator takes longer when the strings
        are similar, which allows a timing attack.  This simple method avoids
        this problem.  The comparison takes always the same time.

        Returns True if both strings arrays are equal. False otherwise.

        """
        diff = len(string1) ^ len(string2)
        for a, b in zip(string1, string2):
            diff |= ord(a) ^ ord(b)
        return diff == 0


class PlainTextPasswordStorage(PasswordStorage):
    """Basic password storage storing passwords in plain text.

    Only use when security does not matter at all.

    """

    def stored_password(self, password):
        return password

    def check_password(self, password, stored_password):
        return self._equals(password, stored_password)


class UnsaltedMd5PasswordStorage(PasswordStorage):
    """Basic password storage storing passwords as unsalted MD5 hashes.

    Only use when security does not really matter, because the stored passwords
    are not salted.  The main purpose is handling the existing passwords which
    were created by older applications.

    """

    def _md5(self, password):
        if isinstance(password, str):
            password = password.encode('utf-8')
        try:
            from hashlib import md5
        except ImportError:
            from md5 import md5
        return md5(password).hexdigest()

    def stored_password(self, password):
        return self._md5(password)

    def check_password(self, password, stored_password):
        return self._equals(self._md5(password), stored_password)


class Pbkdf2PasswordStorage(PasswordStorage):
    """Password storage storing passwords as salted PBKDF2 hashes.

    Secure password storage implementation inspired by
    https://crackstation.net/hashing-security.htm

    Constructor options allow selection of the appropriate security measures in
    a forward compatible manner (when changed, the existing stored passwords
    don't need to be updated).

    """

    def __init__(self, salt_length=32, hash_length=32, iterations=1000):
        """Arguments:
          salt_length -- length of the salt as int (number of characters)
          hash_length -- length of the hash itself as int (number of characters)
          iterations -- number of iterations of the PBKDF2 algorithm

        All parameters may be changed without breaking existing hashes (stored
        in the database).  Only newly created hashes will respect new
        parameters.

        The lengths given by 'salt_length' and 'hash_length' are character
        lengths of the resulting strings.  The strings are hex encoded so each
        byte is represented by two characters.  Thus the actual byte size
        determining strength is a half of the length.

        """
        assert isinstance(salt_length, int), salt_length
        assert isinstance(hash_length, int), hash_length
        assert isinstance(iterations, int), iterations
        self._salt_length = salt_length
        self._hash_length = hash_length
        self._iterations = iterations

    @property
    def salt_length(self):
        return self._salt_length

    @property
    def hash_length(self):
        return self._hash_length

    @property
    def iterations(self):
        return self._iterations

    def stored_password(self, password):
        salt = generate_random_string(self._salt_length)
        iterations = self._iterations
        hashed_password = self._pbkdf2_hash(password, salt, iterations, self._hash_length)
        return ':'.join((str(iterations), salt, hashed_password))

    def check_password(self, password, stored_password):
        iterations, salt, stored_hash = stored_password.split(':')
        try:
            iterations = int(iterations)
        except ValueError:
            return False
        test_hash = self._pbkdf2_hash(password, salt, iterations, len(stored_hash))
        return self._equals(test_hash, stored_hash)

    def _pbkdf2_hash(self, password, salt, iterations, output_characters):
        import pbkdf2
        output_bytes = pbkdf2.PBKDF2(password, salt, iterations).read(output_characters // 2 + 2)
        return ''.join(['%x' % byte for byte in output_bytes])[:output_characters]


class Pbkdf2Md5PasswordStorage(Pbkdf2PasswordStorage, UnsaltedMd5PasswordStorage):
    """Special storage for passwords converted from unsalted MD5 to PBKDF2.

    This storage is used by UniversalPasswordStorage internally for checking
    the passwords converted from unsalted MD5 hashes to salted PBKDF2 hashes.
    It is only useful for conversion of old databases and you will probalby
    never want to use it directly.

    When the original database contains unsalted MD5 hashes and we want to
    improve the security by adding salt to the stored passwords, we need to
    apply salting and hashing on top of the already hashed passwords since we
    don't have access to the original plain text passwords.

    """

    def stored_password(self, password):
        return super(Pbkdf2Md5PasswordStorage, self).stored_password(self._md5(password))

    def check_password(self, password, stored_password):
        return super(Pbkdf2Md5PasswordStorage, self).check_password(self._md5(password),
                                                                    stored_password)


class UniversalPasswordStorage(PasswordStorage):
    """Universal password storage capable of handling passwords in multiple formats.

    This storage stores passwords together with a prefix which determines the
    algorithm used to create the stored version of the password.  This allows
    changing the preferred storage algorithm without breaking the existing
    stored passwords -- they are still checked according to the old algorithm
    even if new passwords are stored with another algorithm.

    """

    def __init__(self, **kwargs):
        self._storage = {
            'plain': PlainTextPasswordStorage(),
            'md5u': UnsaltedMd5PasswordStorage(),
            'pbkdf2': Pbkdf2PasswordStorage(**kwargs),
            'pbkdf2/md5': Pbkdf2Md5PasswordStorage(**kwargs),
        }
        # The storage used for creation of new stored passwords
        # (PBKDF2 is currently the most secure option).
        self._default_prefix = 'pbkdf2'
        self._default_storage = self._storage[self._default_prefix]

    def check_password(self, password, stored_password):
        prefix, stored_password = stored_password.split(':', 1)
        storage = self._storage[prefix]
        return storage.check_password(password, stored_password)

    def stored_password(self, password):
        return self._default_prefix + ':' + self._default_storage.stored_password(password)


def test_password_storage():
    ustorage = wiking.UniversalPasswordStorage()
    for prefix, storage in (('plain', wiking.PlainTextPasswordStorage()),
                            ('md5u', wiking.UnsaltedMd5PasswordStorage()),
                            ('pbkdf2', wiking.Pbkdf2PasswordStorage(5, 9)),
                            ('pbkdf2', wiking.Pbkdf2PasswordStorage(10, 16)),
                            ('pbkdf2', wiking.Pbkdf2PasswordStorage()),
                            ('pbkdf2/md5', wiking.Pbkdf2Md5PasswordStorage()),
                            (None, wiking.UniversalPasswordStorage())):
        for passwd in ('bla', 'xxxxx', 'wer2d544aSWdD5', '34čůdl1G5'):
            stored = storage.stored_password(passwd)
            if prefix == 'pbkdf2':
                assert len(stored) == (len(str(storage.iterations)) + storage.salt_length +
                                       storage.hash_length + 2)
            if prefix not in ('plain',):
                assert stored != passwd
            if prefix not in ('plain', 'md5u'):
                # Check that salting works (two hashes of the same password not equal)
                stored2 = storage.stored_password(passwd)
                assert stored != stored2
                assert storage.check_password(passwd, stored2)
            assert storage.check_password(passwd, stored)
            assert not storage.check_password('xx', stored)
            if prefix:
                assert ustorage.check_password(passwd, prefix + ':' + stored)
                assert not ustorage.check_password('xx', prefix + ':' + stored)


class AuthenticationProvider:
    """Abstract intercace for authentication providers.

    Various authentication mechanisms may be implemented by implementing this
    interface (actualy the method 'authenticate()').

    An application may support multiple authentication providers which may be
    used in a given order of precedence.  This order is defined by the
    configuration option 'authentication_providers' and the logic is
    implemented by 'wiking.Request.user()'.

    Particular implementations handle particular authentication protocols, but
    may be still neutral to application specific authentication and session
    data storage implementation.  The 'Application' module is responsible for
    login name/password verification through the method
    'Application.authenticate()'.  The 'Session' module is responsible
    persisting session information.  See their documentation for more details.

    """

    def authenticate(self, req):
        """Perform authentication and return a 'User' instance if successful.

        This method is called when authentication is needed.  A 'User' instance
        must be returned if authentication was successful or None if not.
        'AuthenticationError' may be raised if authentication credentials are
        supplied but are not correct.  In other cases, None as the returned
        value means, that the user is not logged or that the session expired.

        The only argument is the request object, which may be used to obtain
        authentication credentials, store session cookeis, headers or whatever
        else is needed by the implemented authentication protocol.

        """
        raise NotImplementedError()


class HTTPBasicAuthenticationProvider(AuthenticationProvider):
    """HTTP Basic authentication provider.

    HTTP authentication credentials are sent repetitively for all requests.
    HTTP Basic authentication also doesn't support logout (there is no way to
    tell the user agent to drop the cached credentials).  This makes HTTP
    authentication less secure than other supported options, so this provider
    is not included in the default setup of configuration option
    'authentication_providers'.  However certain clients, such as some RSS
    readers may not support other authentication mechanisms so if you care
    about such clients, you may wish to enable HTTP Basic authentication by
    enabling this provider through the configuration option
    'allow_http_authentication'.

    Cookies can not be used to persist the session key on the client (HTTP
    authentication is typically the only option for clients which don't support
    cookies).  So we use a fixed string instead of a session key.  This makes
    the session shared for all clients of a given user.  Password must be
    verified on every request so this causes no additional security risk.

    Note, that when running on Apache and mod_wsgi, you also need to set the
    Apache configuration option WSGIPassAuthorization to "on" to make HTTP
    authorization work.

    """
    _AUTH_TYPE = 'HTTP-Basic'

    def authenticate(self, req):
        auth_header = req.header('Authorization')
        if not auth_header or not auth_header.startswith('Basic '):
            return None
        try:
            credentials = str(base64.b64decode(auth_header.split()[1]), req.encoding())
        except (binascii.Error, UnicodeError):
            return None
        login, password = credentials.split(":", 1)
        application = wiking.module.Application
        user = application.authenticate(req, login, password, self._AUTH_TYPE)
        if user:
            if wiking.module.Session.init(req, user, self._AUTH_TYPE, reuse=True):
                # Session.init() returns None if previous HTTP-Basic session is reused.
                application.login_hook(req, user)
            return user
        else:
            raise AuthenticationError(_("Invalid login!"))


class CookieAuthenticationProvider(AuthenticationProvider):
    """Cookie based authentication provider.

    The credentials are sent just once (after login form submission).  If these
    credentials are validated sucessfully against the stored credentials for
    given user, a new session is initiated.  The session is identified by a
    session key which is stored on the server as well as on the client.  Server
    side storage is implemented by the 'Session' module, client side storage is
    done using a browser cookie.  The session continues (and authentication is
    accepted) as long as the server side session key matches the client side
    key.  Each succesfull subsequent request refreshes the server side session
    expiration interval.

    Logging in is normally handled by 'LoginDialog', which is automatically
    displayed in response to a request which raises 'AuthenticationError'.
    When a client needs to log in programatically, the parameter '__log_in'
    must be passed together with users login name and password in parameters
    'login' and 'password'.

    """
    _SESSION_COOKIE = 'session'
    _AUTH_TYPE = 'Cookie'
    _IOS10_UA_MATCHER = re.compile(r' OS 10_\d+_\d+ like Mac OS X')

    def authenticate(self, req):
        session = wiking.module.Session
        application = wiking.module.Application
        if req.has_param('__log_in'):
            # Fresh login - login form submitted.
            login = req.param('login')
            if not login:
                raise AuthenticationError(_("Enter your login name, please!"))
            password = req.param('password')
            if not password:
                raise AuthenticationError(_("Enter your password, please!"))
            req.set_param('password', None)
            user = application.authenticate(req, login, password, self._AUTH_TYPE)
            if not user:
                raise AuthenticationError(_("Invalid login!"))
            assert isinstance(user, wiking.User)
            # Login succesfull
            session_key = session.init(req, user, self._AUTH_TYPE)
            application.login_hook(req, user)
            self._set_session_cookie(req, session_key)
        else:
            # Is there an existing session?
            session_key = req.cookie(self._SESSION_COOKIE)
            if session_key:
                user = session.check(req, session_key)
                self._set_session_cookie(req, session_key)
            else:
                user = None
        if req.param('command') == 'logout' and user:
            session.close(req, session_key)
            self._set_session_cookie(req, None)
            application.logout_hook(req, user)
            user = None
        elif req.param('command') == 'login' and not user:
            raise wiking.AuthenticationRedirect()
        return user

    def _set_session_cookie(self, req, session_key):
        # Session cookie expiration is used just to make the cookie persist
        # when the browser is closed.  Cookies which don't expire ('expires'
        # unset) are discarded when the browser is closed.  Note that the
        # expiration of the cookie (client side) is not decisive for the
        # expiration of the session itself.  Session expiration is checked by
        # the session module independently on session cookie verification.  The
        # cookie just should not expire sooner than the session to make the
        # verification work.
        if session_key and (wiking.cfg.persistent_sessions or
                            self._IOS10_UA_MATCHER.search(req.header('User-Agent', ''))):
            # The User-Agent check above is used to detect iOS 10.x devices and
            # force cookie expiration set in this case to work around
            # AppleCoreMedia bug (or missfeature?) which causes media files
            # referenced in <audio> and <video> tags to be downloaded without
            # sending all cookies.  Only cookies with expiration set are sent
            # with the request and others are ignored.  Forcing cookie
            # expiration on iOS 10 devices unfortunately causes the user
            # sessions to be always persistent in this case, but this actually
            # doesn't seem to be a huge problem because the browser is
            # typically never closed on iOS so the users won't expect the
            # session to end unless they explicitly log out.  Also the iOS
            # devices are often personal so the risk of stealing user's session
            # is minimized by their typical usage scenario.  Without this work
            # around, media playback will not work if these media files require
            # authentication.  At this time it is not known whether Apple is
            # going to fix this issue and in which iOS version, so the regexp
            # matches all 10.x iOS versions.  Once this is known, the regexp
            # can be more specific.
            expires = wiking.cfg.session_expiration * 3600
        else:
            expires = None  # Cookie discarded when browser closed.
        req.set_cookie(self._SESSION_COOKIE, session_key, expires=expires,
                       # Don't require HTTPS during development.
                       secure=not wiking.cfg.debug)


# ============================================================================
# Classes derived from LCG components
# ============================================================================


class TopBarControl(lcg.Content):
    """Generic superclass for typical wiking top bar widgets.

    The controls are displayed at the top bar of a Wiking application.  Wiking
    applications may define custom controls derived from this class or from
    lcg.Content directly when the control doesn't share the common properties
    supported by this class.

    The controls derived from this class may have a label, tooltip, displayed
    content and a popup menu, all optional.  Their actual content is defined by
    the return value of the methods '_icon()', '_label()', '_content()',
    '_menu_label()', '_menu_items()' and '_menu_title()'.  If all these methods
    return an empty result, the control is not displayed at all.

    To make use of a particular control in an application, return its instance
    from 'wiking.Application.top_controls()'.

    """

    def _icon(self, context):
        """Return the string identifier of the icon displayed before the control or None.

        The icon is only added when '_content()' or '_menu_items()' returns a
        non-empty result.

        """
        return None

    def _label(self, context):
        """Return the label displayed before the control or None for unlabeled control.

        The label is only added when '_content()' or '_menu_items()' returns a
        non-empty result.

        """
        return None

    def _content(self, context):
        """Return the content displayed within the control.

        This content is displayed between the label and the menu.

        Returns the exported content as a str or HtmlEscapedUnicode if
        the content contains HTML tags.  If None is returned, nothing is
        displayed.

        """
        return None

    def _menu_items(self, context):
        """Return the menu items displayed in the control's popup menu.

        Returns a sequence of 'lcg.PopupMenuItem' instances.  When the returned
        sequence is empty, the control will not display a popup menu.

        """
        return []

    def _menu_label(self, context):
        """Return the current value displayed within the control's popup menu.

        The label is displayed together with the popup arrow and typically
        displays the current value selected from the menu (when this makes
        sense) or other information about the current state of the control.

        Returns the exported content as a str or HtmlEscapedUnicode if
        the content contains HTML tags.  If None is returned, nothing is
        displayed.

        """
        return None

    def _menu_title(self, context):
        """Return a short and descriptive title of the control's popup menu.

        This title is used as an accessible label of the menu invocation
        control (the down pointing arrow) as well as its tooltip.

        """
        return None

    def export(self, context):
        g = context.generator()
        result = []
        content = self._content(context)
        if content:
            result.append(g.span(content, cls='ctrl-content'))
        items = self._menu_items(context)
        if items:
            menu_label = self._menu_label(context)
            menu_title = self._menu_title(context)
            menu = lcg.PopupMenuCtrl(menu_title, items, content=HtmlContent(menu_label or ''))
            result.append(menu.export(context))
        if result:
            label = self._label(context)
            if label:
                result.insert(0, g.span(label, cls='ctrl-label'))
            icon = self._icon(context)
            if icon:
                result.insert(0, g.span('', cls='ctrl-icon %s-icon' % icon))
            return g.span(result, cls=pytis.util.camel_case_to_lower(self.__class__.__name__, '-'))
        else:
            return ''


class LoginControl(TopBarControl):
    """Login control widget.

    The login control is typically displayed at the top bar of a Wiking
    application.  Specific Wiking applications may customize the login control
    by overriding this class and returning an instance of the derived class in
    'wiking.Application.top_controls()'.

    """

    def _icon(self, context):
        return 'user-larger'

    def _menu_title(self, context):
        if context.req().user():
            return _("User actions")
        else:
            return _("Login and registration")

    def _menu_items(self, context):
        req = context.req()
        user = req.user()
        items = []
        if user:
            if user.uri():
                g = context.generator()
                login, displayed_name = user.login(), user.name()
                if login != displayed_name:
                    displayed_name += ' (' + login + ')'
                label = g.div((g.div(displayed_name, cls='user-name'),
                               # Translators: Menu item label to display a page with
                               # details of user's account and related actions.
                               g.div(_("My user profile"), cls='user-label')))
                items.append(lcg.PopupMenuItem(label, uri=user.uri(), icon='user-icon',
                                               cls='user-profile'))
            password_change_uri = wiking.module.Application.password_change_uri(req)
            if password_change_uri:
                # Translators: Menu item label.
                items.append(lcg.PopupMenuItem(_("Change my password"), icon='key-icon',
                                               uri=password_change_uri))
            # Translators: Menu item label (verb in imperative).
            items.append(lcg.PopupMenuItem(_("Log out"), icon='circle-out-icon',
                                           uri=req.make_uri(req.uri(), command='logout')))
        elif wiking.cfg.show_login_control:
            items.extend([
                lcg.PopupMenuItem(title, icon=icon, tooltip=tooltip, uri=uri)
                for title, tooltip, icon, uri in (
                    (_("Log in"), _("Log in to an existing user account"), 'circle-in-icon',
                     req.make_uri(req.uri(), command='login')),
                    # Translators: Link/menu item to create a new
                    # user account to access the website/application.
                    (_("Register a new user account"), None, 'new-user-icon',
                     wiking.module.Application.registration_uri(req)),
                    # Translators: Link/menu item to restore a forgotten password.
                    (_("Restore forgotten password"), None, 'key-icon',
                     wiking.module.Application.forgotten_password_uri(req)),
                ) if uri])
        return items

    def _menu_label(self, context):
        g = context.generator()
        req = context.req()
        user = req.user()
        if user:
            login, displayed_name = user.login(), user.name()
            # Translators: Login status info.
            tooltip = _("Logged in user:") + ' ' + displayed_name
            if login != displayed_name:
                tooltip += ' (' + login + ')'
            result = g.span(displayed_name, cls='displayed-user-name', title=tooltip)
        else:
            result = None
        return result

    def _content(self, context):
        req = context.req()
        user = req.user()
        if user:
            password_expiration = user.password_expiration()
            if password_expiration:
                g = context.generator()
                msg_id = context.unique_id()
                return g.div(
                    (g.span('!', cls='badge', aria_hidden='true'),
                     g.div((g.span('', cls='warning-icon'),
                            # Translators: Login panel info. '%(date)s'
                            # is replaced by a concrete date.
                            _("Your password expires on %(date)s",
                              date=lcg.LocalizableDateTime(password_expiration))),
                           id=msg_id, cls='info', style='display: none')),
                    cls='password-expiration-warning',
                    aria_labelledby=msg_id, aria_role='note',
                )
        elif wiking.cfg.show_login_control:
            g = context.generator()
            uri = req.uri()
            if uri.endswith('_registration'):
                uri = '/'  # Redirect logins from the registration forms to site root
            # Translators: Login button label (verb in imperative).
            return g.a(g.span('', cls='ctrl-icon circle-in-icon') + _("Log in"),
                       href=g.uri(uri, command='login'), cls='login-button', role='button',
                       # Translators: Login status info.
                       title=_("User not logged in"))
        return None


class LanguageSelection(TopBarControl):
    """Language selection widget.

    The language selection widget is typically displayed at the top bar of a
    Wiking application when the page is available in multiple language
    variants.  Wiking applications may need to customize the language control
    by overriding this class and returning an instance of the derived class in
    'wiking.Application.top_controls()'.

    """

    def _label(self, context):
        # Translators: Label for language selection followed by the
        # current language name with a selection of other available
        # language variants.
        return _("Language:")

    def _menu_title(self, context):
        return _("Switch the language")

    def _menu_items(self, context):
        node = context.node()
        variants = node.variants()
        e = context.exporter()
        return [lcg.PopupMenuItem(e.localizer(lang).localize(lcg.language_name(lang) or lang),
                                  uri=e.uri(context, node, lang=lang),
                                  cls='lang-' + lang + ' current' if lang == context.lang() else '')
                for lang in sorted(variants)]

    def _menu_label(self, context):
        g = context.generator()
        lang = context.lang()
        # The language code CS for Czech is very confusing for ordinary
        # users, while 'CZ' (which is actually a country code) seems much
        # more familiar...
        abbr = dict(cs='CZ').get(lang, lang.upper())
        return lcg.concat(
            g.span(lcg.language_name(lang) or abbr, cls='language-name'),
            g.span(abbr, cls='language-abbr'),
        )

    def export(self, context):
        if len(context.node().variants()) <= 1:
            return ''
        return super(LanguageSelection, self).export(context)


class MaximizedModeControl(TopBarControl):
    """Maximized mode control.

    Turns on/off the "maximized mode".  The Maximized mode makes the main
    content to span to the full width, reducing the side bars (tree menu on the
    left and panels on the right side).

    """

    def _content(self, context):
        g = context.generator()
        if context.req().maximized():
            label = _("Exit the maximized mode.")
            href = '?maximize=0'
            icon = 'unmaximize-icon'
        else:
            label = _("Maximize the main content to the full size of the browser window.")
            href = '?maximize=1'
            icon = 'maximize-icon'
        return g.a(g.span('', cls=icon), href=href, title=label, aria_label=label, role='button')


class LoginDialog(lcg.Content):
    """Login dialog for entering login name and password."""

    def __init__(self, registration_uri=None, forgotten_password_uri=None,
                 top_content=None, bottom_content=None, login_is_email=False):
        self._registration_uri = registration_uri
        self._forgotten_password_uri = forgotten_password_uri
        self._top_content = top_content
        self._bottom_content = bottom_content
        self._login_is_email = login_is_email
        super(LoginDialog, self).__init__()

    def export(self, context):
        g = context.generator()
        req = context.req()
        ids = context.id_generator()

        def hidden_field(name, value):
            if isinstance(value, str):
                return g.hidden(name=name, value=value)
            elif isinstance(value, (tuple, list)):
                return lcg.concat([hidden_field(name, v) for v in value], separator="\n")
            else:
                # This may be a file field, or anything else?
                # TODO: Is it a good idea to leave the field out without a warning?
                return ''
        if self._login_is_email:
            login_label = _("Your e-mail address")
            login_type = 'email'
        else:
            login_label = _("Login name")
            login_type = 'text'
        content = [
            hidden_field(param, req.param(param))
            for param in req.params() if param not in ('command', 'login', 'password', '__log_in')
        ] + [
            g.label(login_label + ':', for_=ids.login) + g.br(),
            g.input(type=login_type, name='login', value=req.param('login'),
                    id=ids.login, size=18, maxlength=64,
                    autocomplete='username', autofocus=True),
            g.br(),
            g.label(_("Password") + ':', for_=ids.password) + g.br(),
            g.input(type='password', name='password', id=ids.password, size=18, maxlength=32,
                    autocomplete='current-password'),
            g.br(),
            g.hidden(name='__log_in', value='1'),
            # Translators: Login button label - verb in imperative.
            g.button(g.span(_("Log in")), type='submit', cls='submit'),
        ]
        links = [g.li(g.a(label, href=uri)) for label, uri in
                 ((_("Register a new user account"), self._registration_uri),
                  (_("Restore forgotten password"), self._forgotten_password_uri)) if uri]
        if links:
            content.append(g.ul(*links))
        if not req.https() and wiking.cfg.force_https_login:
            uri = req.server_uri(force_https=True) + (req.root() or '') + req.uri()
        else:
            uri = (req.root() or '') + req.uri()
        result = (g.form(content, method='POST', action=uri, name='login_form', cls='login-form',
                         novalidate=True) +
                  # The script below is redundant in browsers supporting <input>
                  # autofocus attribute but we need it for legacy browsers.
                  g.script("onload_ = window.onload; window.onload = function() { "
                           "if (onload_) onload_(); "
                           "setTimeout(function () { document.login_form.login.focus() }, 0); };"))
        if self._top_content:
            result = g.div(lcg.coerce(self._top_content).export(context),
                           cls='login-dialog-content login-dialog-top-content') + result
        if self._bottom_content:
            result += g.div(lcg.coerce(self._bottom_content).export(context),
                            cls='login-dialog-content login-dialog-bottom-content')
        return result


class DecryptionDialog(lcg.Content):
    """Password dialog for entering a decryption password."""

    def __init__(self, name):
        assert isinstance(name, str)
        self._decryption_name = name
        super(DecryptionDialog, self).__init__()

    def export(self, context):
        g = context.generator()
        req = context.req()
        # Translators: Web form label and message
        message = _("Decryption password for '%s'", self._decryption_name)
        content = (
            g.label(message + ':', '__decryption_password') + g.br(),
            g.input(name='__decryption_password', id='__decryption_password', password=True,
                    size=18, maxlength=32),
            g.br(),
            # Translators: Web form button.
            g.button(g.span(_("Send password")), type='submit', cls='submit'),
        )
        if req.https():
            uri = req.uri()
        else:
            uri = req.server_uri(force_https=True) + req.uri()
        result = (g.form(content, method='POST', action=uri, name='decryption_form',
                         cls='login-form') +
                  g.script("onload_ = window.onload; window.onload = function() { "
                           "if (onload_) onload_(); "
                           "setTimeout(function () { "
                           "document.decryption_form.__decryption_password.focus() }, 0); };"))
        return result


class ConfirmationDialog(lcg.Container):
    """Dialog displaying arbitrary content followed by a `Continue' button."""

    def export(self, context):
        g = context.generator()
        return g.div((super(ConfirmationDialog, self).export(context),
                      # Translators: Confirmation button
                      g.form(g.button(g.span(_("Continue")), type='submit'),
                             method='GET', action=context.req().uri(), cls='confirmation-form')),
                     cls='confirmation-dialog')


class HtmlContent(lcg.TextContent):
    """LCG content class for wrapping already exported HTML text.

    This class allows embedding HTML content into the LCG content hierarchy.
    Its export is a noop.  It denies all the advantages of the LCG's export
    separation, so use only when there is no other choice and with caution.

    """

    def export(self, context):
        return self._text


class Message(lcg.Container):
    """Distinguishable message displayed within other content.

    The message may be pure text (passing 'str' as 'content' to the
    constructor) or any 'lcg.Content' instance.  Messages may also use inline
    formatting when the argument 'formatted' is True as in 'lcg.coerce()'.

    The message will be displayed inside a distinguishable box with an icon.
    The 'kind' agrument of the constructor determines the colors and icon of
    the box.  Available kinds are defined by class constants below.

    """
    INFO = 'info'
    """Message 'kind' constant for informational messages."""
    SUCCESS = 'success'
    """Message 'kind' constant for success messages."""
    WARNING = 'warning'
    """Message 'kind' constant for warning messages."""
    ERROR = 'error'
    """Message 'kind' constant for error messages."""

    def __init__(self, content, formatted=False, kind=INFO, name=None, **kwargs):
        assert kind in (self.INFO, self.SUCCESS, self.WARNING, self.ERROR)
        icon = lcg.HtmlContent(lambda context, element: self._export_icon(context))
        if formatted and isinstance(content, lcg.Localizable):
            # Parsing must be done after localization, but lcg.coerce()
            # does parsing first.  Maybe lcg.coerce() should be changed
            # this way, but it might have unknown consequences...
            class FormattedString(lcg.TextContent):

                def export(self, context):
                    localized_text = context.localize(self._text)
                    return lcg.Parser().parse_inline_markup(localized_text).export(context)
            content = FormattedString(content)
        else:
            content = lcg.coerce(content, formatted=formatted)
        super(Message, self).__init__((icon, lcg.Container(content, name='content')),
                                      name=' '.join(('message', kind) + ((name,) if name else ())),
                                      **kwargs)
        self._kind = kind

    def _export_icon(self, context):
        g = context.generator()
        return g.span(g.span('', cls='%s-icon' % self._kind), cls='icon')


class IFrame(lcg.Content):
    """HTML specific IFRAME component."""

    def __init__(self, uri, width=400, height=200):
        self._uri = uri
        self._width = width
        self._height = height
        super(IFrame, self).__init__()

    def export(self, context):
        return context.generator().iframe(self._uri, width=self._width, height=self._height)


# ============================================================================
# Classes derived from Pytis components
# ============================================================================

class WikingDefaultDataClass(DBAPIData):
    """Default data class used by wiking modules connected to pytis data objects.

    Web applications don't use pytis access rights, since they always access the database as one
    system user (the web server).  Wiking authentication and authorization logic is implemented
    completely within Wiking modules and doesn't penetrate to the pytis layer.  We can't use the
    default data class defined by pytis, because it implements pytis access restrictions, so we
    define a Wiking specific class derived just from the basic pytis data accessor class.

    Apart from the unresticted access described above, this class only implements a few helper
    methods which make data access bit easier.

    """

    def __init__(self, *args, **kwargs):
        super(WikingDefaultDataClass, self).__init__(*args, **kwargs)
        # We don't want to care how `connection_data' is stored in the parent class...
        self._dbconnection = kwargs['connection_data'].select(kwargs.get('connection_name'))

    def _row_data(self, **kwargs):
        def t(colname):
            column = self.find_column(colname)
            assert column is not None, \
                "Unknown column '%s' in '%s'" % (colname, self.table(self.key()[0].id()))
            return column.type()
        return [(k, pd.Value(t(k), v)) for k, v in kwargs.items()]

    def get_rows(self, skip=None, limit=None, sorting=(), condition=None, arguments=None,
                 columns=None, transaction=None, **kwargs):
        if kwargs:
            conds = [pd.EQ(k, v) for k, v in self._row_data(**kwargs)]
            if condition:
                conds.append(condition)
            condition = pd.AND(*conds)
        try:
            self.select(condition=condition, sort=sorting, arguments=arguments, columns=columns,
                        transaction=transaction)
            rows = []
            if skip:
                self.skip(skip)
            while True:
                row = self.fetchone()
                if row is None:
                    break
                rows.append(row)
                if limit is not None and len(rows) >= limit:
                    break
        finally:
            try:
                self.close()
            except Exception:
                pass
        return rows

    def get_row(self, **kwargs):
        rows = self.get_rows(**kwargs)
        if len(rows) == 0:
            return None
        else:
            return rows[0]

    def make_row(self, **kwargs):
        return pd.Row(self._row_data(**kwargs))

    def _update_cached_tables(self):
        try:
            cached_tables = wiking.module.CachedTables
        except AttributeError:
            # The module may not be available in applications which don't
            # use Wiking CMS or caching explicitly.
            pass
        else:
            cached_tables.reload_info(None)

    def insert(self, *args, **kwargs):
        result = super(WikingDefaultDataClass, self).insert(*args, **kwargs)
        self._update_cached_tables()
        return result

    def insert_many(self, *args, **kwargs):
        result = super(WikingDefaultDataClass, self).insert_many(*args, **kwargs)
        self._update_cached_tables()
        return result

    def update(self, *args, **kwargs):
        result = super(WikingDefaultDataClass, self).update(*args, **kwargs)
        self._update_cached_tables()
        return result

    def update_many(self, *args, **kwargs):
        result = super(WikingDefaultDataClass, self).update_many(*args, **kwargs)
        self._update_cached_tables()
        return result

    def delete(self, *args, **kwargs):
        result = super(WikingDefaultDataClass, self).delete(*args, **kwargs)
        self._update_cached_tables()
        return result

    def delete_many(self, *args, **kwargs):
        result = super(WikingDefaultDataClass, self).delete_many(*args, **kwargs)
        self._update_cached_tables()
        return result


class Specification(pp.Specification):
    help = None  # Default value needed by CMSModule.descr()
    actions = []
    data_cls = WikingDefaultDataClass

    def __init__(self, wiking_module):
        self._module = wiking_module
        if self.table is None:
            self.table = pytis.util.camel_case_to_lower(wiking_module.name(), '_')
        actions = self.actions
        if callable(actions):
            actions = actions()
        actions = list(actions)
        for base in wiking_module.__bases__ + (wiking_module,):
            # Using the _ACTIONS module attribute is DEPRECATED!
            if hasattr(base, '_ACTIONS'):
                for action in base._ACTIONS:
                    if action not in actions:
                        actions.append(action)
        self.actions = tuple(actions)
        super(Specification, self).__init__()

    def _action_spec_name(self):
        # Mainly to indicate the module name in specification error messages...
        return self._module.__module__ + '.' + self._module.name()


class Binding(pp.Binding):
    """Extension of Pytis 'Binding' with web specific parameters."""

    def __init__(self, *args, **kwargs):
        """Arguments:

          form -- the form class or none for the default form.  If used, must be a class derived
            from 'pytis.web.Form'.

        Other arguments are same as in the parent class.

        """
        form = kwargs.pop('form', None)
        super(Binding, self).__init__(*args, **kwargs)
        if isinstance(form, tuple):
            form_cls, form_kwargs = form
            assert issubclass(form_cls, pytis.web.Form), form_cls
            assert isinstance(form_kwargs, dict), form_kwargs
        else:
            assert form is None or issubclass(form, pytis.web.Form), form
            form_cls = form
            form_kwargs = {}
        self._form_cls = form_cls
        self._form_kwargs = form_kwargs

    def form_cls(self):
        return self._form_cls

    def form_kwargs(self):
        return self._form_kwargs


class WikingResolver(pytis.util.Resolver):
    """A custom resolver of Wiking modules."""
    _wiking_module_instance_cache = {}
    _wiking_module_class_cache = {}

    def _get_specification(self, key):
        name, kwargs = key
        module_cls = self.wiking_module_cls(name)
        return module_cls.Spec(module_cls, **dict(kwargs))

    def _get_object_by_name(self, name):
        # Temporary hack
        if name.startswith('cms.'):
            import wiking
            return wiking.cms.Users
        else:
            return super(WikingResolver, self)._get_object_by_name(name)

    def wiking_module_cls(self, name):
        """Return the Wiking module class of given 'name'."""
        try:
            module_cls = self._wiking_module_class_cache[name]
        except KeyError:
            module_cls = self._get_object_by_name(name)
            self._wiking_module_class_cache[name] = module_cls
        return module_cls

    def wiking_module(self, name, **kwargs):
        """Return the instance of a Wiking module given by 'name'.

        Any keyword arguments are be passed to the module constructor.  The
        instances are cached internally (for matching constructor arguments).

        """
        key = (name, tuple(kwargs.items()))
        try:
            module_instance = self._wiking_module_instance_cache[key]
            # TODO: Check the class definition for changes and reload in runtime?
            # if module_instance.__class__ is not cls:
            #     # Dispose the instance if the class definition has changed.
            #     raise KeyError()
        except KeyError:
            cls = self.wiking_module_cls(name)
            module_instance = cls(name, **kwargs)
            self._wiking_module_instance_cache[key] = module_instance
        return module_instance

    def available_modules(self):
        """Return a tuple of classes of all available Wiking modules."""
        return [module_cls for name, module_cls in self.walk(wiking.Module)]


class ModuleInstanceResolver:
    """Single purpose class to be used as 'wiking.module' instance (see below)."""

    def __call__(self, name):
        return wiking.cfg.resolver.wiking_module(name)

    def __getattr__(self, name):
        if name.startswith('_'):
            return super(ModuleInstanceResolver, self).__getattr__(name)
        else:
            try:
                return wiking.cfg.resolver.wiking_module(name)
            except pytis.util.ResolverError as e:
                raise AttributeError(str(e))


module = ModuleInstanceResolver()
"""Return the instance of given Wiking module.

This callable object may be used to retrieve instances of Wiking modules of the
current application.  It may be either called as a function with module name as
an argument or accessed using module names as its attributes.

Raises: wiking.util.ResolverError if no such module is found in the current
resolver configuration.

This is the official way to retrieve Wiking modules within the application.
All other means, such as the method 'Module._module()' or using
wiking.cfg.resolver directly are deprecated.

"""


class DateTime(pytis.data.DateTime):
    """Deprecated.  Use 'pytis.data.DateTime' directly."""

    def _init(self, show_time=True, exact=False, leading_zeros=True, **kwargs):
        self._exact = exact
        self._show_time = show_time
        self._leading_zeros = leading_zeros
        format = '%Y-%m-%d %H:%M'
        if exact:
            format += ':%S'
        super(DateTime, self)._init(format=format, **kwargs)

    def exact(self):
        return self._exact

    def _export(self, value, show_weekday=False, show_time=None, **kwargs):
        result = super(DateTime, self)._export(value, **kwargs)
        if show_time is None:
            show_time = self._show_time
        return lcg.LocalizableDateTime(result, show_weekday=show_weekday, utc=self._utc,
                                       show_time=show_time, leading_zeros=self._leading_zeros)


# We need three types, because we need to derive from two different base classes.

class Date(pytis.data.Date):
    """Deprecated.  Use 'pytis.data.Date' directly."""

    def _init(self, leading_zeros=True, **kwargs):
        self._leading_zeros = leading_zeros
        super(Date, self)._init(format='%Y-%m-%d', **kwargs)

    def _export(self, value, show_weekday=False, **kwargs):
        result = super(Date, self)._export(value, **kwargs)
        return lcg.LocalizableDateTime(result, show_weekday=show_weekday,
                                       leading_zeros=self._leading_zeros)


class Time(pytis.data.Time):
    """Deprecated.  Use 'pytis.data.Time' directly."""

    def _init(self, exact=False, **kwargs):
        self._exact = exact
        format = '%H:%M'
        if exact:
            format += ':%S'
        super(Time, self)._init(format=format, **kwargs)

    def exact(self):
        return self._exact

    def _export(self, value, **kwargs):
        return lcg.LocalizableTime(super(Time, self)._export(value, **kwargs))


class TZInfo(datetime.tzinfo):
    """Timezone given by numeric UTC offsets in minutes.

    The results may be inaccurate because we need to assume what the DST
    change times *most likely* are.  In most cases, however, DST lasts from
    the last Sunday in March until the last Sunday in October in modern
    timezones.  Using this class when this assumption doesn't apply is a
    fault.

    This class mainly exists to allow specification of the configuration option
    'default_timezone'.

    # Example: Central Europe has 120 minutes UTC offset in summer and 60 in winter.
    default_timezone = wiking.TZInfo(120, 60)

    """

    def __init__(self, summer_offset, winter_offset):
        """Arguments:

        summer_offset -- summer UTC offset in minutes
        winter_offset -- winter UTC offset in minutes

        Offsets are positive to the East of GMT and negative to the West.

        """
        self._summer_offset = summer_offset
        self._winter_offset = winter_offset

    def _offset(self, dt):
        d1 = datetime.datetime(dt.year, 4, 1)
        dst_start = d1 - datetime.timedelta(days=d1.weekday() + 1)
        d2 = datetime.datetime(dt.year, 11, 1)
        dst_end = d2 - datetime.timedelta(days=d2.weekday() + 1)
        if dst_start <= dt.replace(tzinfo=None) < dst_end:
            return self._summer_offset
        else:
            return self._winter_offset

    def utcoffset(self, dt):
        return datetime.timedelta(minutes=self._offset(dt))

    def tzname(self, dt):
        offset = self._offset(dt)
        sign = offset / abs(offset)
        div, mod = divmod(abs(offset), 60)
        if mod:
            return "GMT %+d:%d" % (div * sign, mod)
        else:
            return "GMT %+d" % div * sign

    def dst(self, dt):
        return self.utcoffset(dt) - datetime.timedelta(minutes=self._winter_offset)


class InputForm(pytis.web.EditForm):

    def __init__(self, req, specification_kwargs, prefill=None, action=None,
                 hidden_fields=(), name='InputForm', new=True, **kwargs):
        class Spec(pp.Specification):
            data_cls = pytis.data.RestrictedMemData

        class Record(pp.PresentedRow):

            def req(self):
                return req
        for key, value in specification_kwargs.items():
            if callable(value):
                # This is necessary to avoid calling functions (such as 'check'
                # or 'row_style') as methods.
                function = value
                if len(pytis.util.argument_names(function)) > 0:
                    # This is an ugly hack.  It is necessary to make the introspection
                    # in Specification.__init__ work.  It actually makes sure that the
                    # condition len(argument_names(value)) == 0 returns the same results
                    # for 'value' and for 'function'.
                    def value(self, x, *args, **kwargs):
                        return function(x, *args, **kwargs)
                else:
                    def value(self, *args, **kwargs):
                        return function(*args, **kwargs)
            setattr(Spec, key, value)
        specification = Spec(wiking.cfg.resolver)
        view_spec = specification.view_spec()
        data_spec = specification.data_spec()
        data = data_spec.create()
        record = Record(view_spec.fields(), data, None, prefill=prefill,
                        resolver=wiking.cfg.resolver, new=new)
        hidden_fields += (('action', action),
                          ('submit', 'submit'))
        super().__init__(view_spec, req, lambda *args: req.uri(), record,
                         name=name, hidden=hidden_fields, **kwargs)


# ============================================================================
# Misc functions
# ============================================================================


def serve_file(req, path, content_type=None, filename=None, lock=False, headers=(),
               allow_redirect=True):
    """Return 'wiking.Response' instance to send the contents of a given file to the client.

    Arguments:
      path -- Full path to the file in server's filesystem.
      content_type -- The value to be used for the 'Content-Type' HTTP header
        (str).  If None, the type will be automatically guessed using the
        python mimetypes module.
      filename -- File name to be used for the 'Content-Disposition' HTTP header.
         This will force the browser to save the file under given file name instead
         of displaying it.
      lock -- Iff True, shared lock will be aquired on the file while it is served.
      headers -- HTTP headers to pass to 'wiking.Response' as a sequence of pairs
        NAME, VALUE (strings).
      allow_redirect -- Allow internal server redirect for file download
        acceleration (file download is actually handled by the frontend server
        and the application process is not blocked by the download).  When the
        redirect is performed, the caller will not be able to further process
        the response.  So if the caller needs to process the returned response,
        redirection must be forbiden using this argument.

    'wiking.NotFound' exception is raised if the file does not exist.

    Important note: The file size is read in advance to determine the Content-Lenght header.
    If the file is changed before it gets sent, the result may be incorrect.

    Internal rediredtion (as described in 'allow_redirect') is only performed,
    when the server is actually configured for it on given file path.  If the
    file path doesn't match one of the directories configured in
    'xsendfile_paths' or 'xaccel_paths' the file will be served using the
    native python implementation.

    Byte range requests are supported by the native implementation, so if the
    request contains the 'Range' header, the response will contain only the
    requested portion of the file (and the HTTML status code will be 206
    instead of 200) according to HTTP protocol specification.  If the 'Range'
    header format can not be read, it will be ignored (the whole file will be
    served).

    """
    try:
        info = os.stat(path)
    except OSError:
        log(OPR, "File not found:", path)
        raise wiking.NotFound()
    if content_type is None:
        mime_type, encoding = mimetypes.guess_type(path)
        content_type = mime_type or 'application/octet-stream'
    if allow_redirect:
        for prefix in wiking.cfg.xsendfile_paths:
            if path.startswith(prefix):
                return wiking.Response('', content_type=content_type, filename=filename,
                                       headers=headers + (('X-Sendfile', path),))
        for prefix, base_uri in wiking.cfg.xaccel_paths:
            if path.startswith(prefix):
                rel_uri = '/'.join(path[len(prefix.rstrip(os.sep)):].split(os.sep))
                uri = base_uri.rstrip('/') + rel_uri
                return wiking.Response('', content_type=content_type, filename=filename,
                                       headers=headers + (('X-Accel-Redirect', uri),))
    offset = limit = None
    status_code = http.client.OK
    content_length = info.st_size
    range_request = req.header('Range')
    if range_request and range_request.strip().startswith('bytes='):
        bounds = range_request[6:].strip().split('-')
        try:
            range_start, range_end = [int(x.strip()) for x in bounds]
        except (ValueError, TypeError):
            pass
        else:
            if range_start >= 0 and range_end >= range_start:
                offset = range_start
                limit = min(range_end + 1, info.st_size) - range_start
                status_code = http.client.PARTIAL_CONTENT
                content_length = limit
                headers += ('Content-Range', 'bytes %s-%d/%d' %
                            (range_start, min(range_end, info.st_size - 1), info.st_size)),

    def generator(offset=None, limit=None):
        f = open(path, 'rb')
        if lock:
            import fcntl
            fcntl.lockf(f, fcntl.LOCK_SH)
        try:
            if offset:
                f.seek(offset)
            while True:
                # Read the file in max 0.5MB chunks.
                read_bytes = 524288
                if limit is not None:
                    read_bytes = min(read_bytes, limit)
                data = f.read(read_bytes)
                if not data:
                    break
                if limit is not None:
                    limit -= len(data)
                yield data
        finally:
            if lock:
                fcntl.lockf(f, fcntl.LOCK_UN)
            f.close()
    return wiking.Response(generator(offset, limit), status_code=status_code,
                           content_type=content_type, content_length=content_length,
                           last_modified=datetime.datetime.utcfromtimestamp(info.st_mtime),
                           filename=filename, headers=headers)


def ajax_response(req, form):
    """Call form.ajax_response() and translate the result to a Wiking response.

    Arguments:
       req -- 'wiking.Request' instance.
       form -- 'pytis.web.EditForm' instance.

    """
    try:
        response = form.ajax_response(req)
    except pytis.web.BadRequest:
        raise wiking.BadRequest()
    if isinstance(response, lcg.Content):
        return response
    else:
        return wiking.Response(json.dumps(response), content_type='application/json')


def timeit(func, *args, **kwargs):
    """Measure the function execution time.

    Invokes the function 'func' with given arguments and returns the triple
    (function result, processor time, wall time), both times in microseconds.

    """
    t1, t2 = time.clock(), time.time()
    result = func(*args, **kwargs)
    return result, time.clock() - t1, time.time() - t2


class MailAttachment:
    """Definition of a mail attachment.

    Mail attachment is defined by the following attributes, given in the class
    instance constructor:

      type -- MIME type of the attachment, as a string
      file_name -- file name of the attachment as a string, this argument must
        be always provided
      stream -- stream to read the given attachment from; if it is unspecified
        the contents file specified by 'file_name' is used

    """

    def __init__(self, file_name, stream=None, type='application/octet-stream'):
        assert file_name is None or isinstance(file_name, str), ('type error', file_name,)
        assert stream is None or hasattr(stream, 'read'), ('type error', stream,)
        assert isinstance(type, str), ('type error', type,)
        self._file_name = file_name
        if stream is None:
            self._stream = open(file_name)
        else:
            self._stream = stream
        self._type = type

    def file_name(self):
        """Return relative or full name of the attachment."""
        return self._file_name

    def stream(self):
        """Return the attachment data source as a file-like object."""
        return self._stream

    def type(self):
        """Return MIME type of the attachment."""
        return self._type


def send_mail(addr, subject, text, sender=None, sender_name=None, html=None,
              export=False, lang=None, cc=(), headers=(), attachments=(),
              smtp_server=None, smtp_port=None, uid=None):
    """Send a MIME e-mail message.

    Arguments:

      addr -- recipient address as a string or sequence of recipient addresses
      subject -- message subject as a string
      text -- message text as a string
      sender -- sender email address as a string; if None, the address
        specified by the configuration option `default_sender_address' is used.
      sender_name -- optional human readable sender name as a string; if not
        None, the name will be added to the 'From' header in the standard form:
        "sender name" <sender@email>.  Proper encoding is taken care of when
        necessary.
      html -- HTML part of the message as string
      export -- iff true, create the HTML part of the message by parsing 'text'
        as LCG Structured text and exporting it to HTML.
      lang -- ISO language code as a string; if not None, message 'subject',
         'text' and 'html' will be translated into given language (if they are
         LCG translatable strings)
      cc -- sequence of other recipient string addresses
      headers -- additional headers to insert into the mail; it must be a tuple
        of pairs (HEADER, VALUE) where HEADER is an ASCII string containing the
        header name (without the final colon) and value is a string containing
        the header value
      attachments -- sequence of 'MailAttachment' instances describing the
        objects to attach to the mail
      smtp_server -- SMTP server name to use for sending the message as a
        string; if 'None', server given in configuration is used
      smtp_port -- SMTP port to use for sending the message as a number; if
        'None', server given in configuration is used
      uid -- if not 'None' then special CC addresses defined in
        'wiking.cfg.special_cc_addresses' are added if the given uid is not in
        any of the 'wiking.cfg.special_cc_exclude_roles'.

    """
    assert isinstance(addr, (str, tuple, list)), ('type error', addr,)
    assert isinstance(subject, str), ('type error', subject,)
    assert isinstance(text, str), ('type error', text,)
    assert sender is None or isinstance(sender, str), ('type error', sender,)
    assert sender_name is None or isinstance(sender_name, str), ('type error', sender_name,)
    assert html is None or isinstance(html, str), ('type error', html,)
    assert isinstance(export, bool), ('type error', bool,)
    assert lang is None or isinstance(lang, str), ('type error', lang,)
    assert isinstance(cc, (tuple, list)), ('type error', cc,)
    assert smtp_server is None or isinstance(smtp_server, str), ('type error', smtp_server,)
    assert smtp_port is None or isinstance(smtp_port, int), ('type error', smtp_port,)
    assert uid is None or isinstance(uid, int), uid
    assert all(isinstance(a, MailAttachment) for a in attachments), attachments
    if isinstance(addr, (tuple, list)):
        addr = ', '.join(addr)
    from email.mime.multipart import MIMEMultipart
    from email.header import Header
    if attachments:
        multipart_type = 'mixed'
    else:
        multipart_type = 'alternative'
    localizer = lcg.Localizer(lang, translation_path=wiking.cfg.translation_path)

    text = localizer.localize(text)
    if not sender or sender == '-':  # Hack: '-' is the Wiking CMS Admin default value...
        sender = wiking.cfg.default_sender_address
    if sender_name:
        sender = '"%s" <%s>' % (sender_name, sender)
    if uid is not None:
        if wiking.cfg.special_cc_addresses:
            # `Users' is in wiking.cms, but we probably don't want to make
            # wiking.cms.send_mail because of this, do we?
            user_roles = wiking.module.Users.user(uid=uid).roles()
            special_roles = wiking.cfg.special_cc_exclude_roles
            if not set(user_roles).intersection(set(special_roles)):
                cc = tuple(cc) + tuple(wiking.cfg.special_cc_addresses)
    # Set up message headers.
    msg = MIMEMultipart(multipart_type)
    msg['From'] = sender
    msg['To'] = addr
    if cc:
        msg['Cc'] = ', '.join(cc)
    msg['Subject'] = localizer.localize(subject)
    msg['Date'] = time.strftime("%a, %d %b %Y %H:%M:%S %z")
    for header, value in headers:
        msg[header] = value
    # The plain text section.
    from email.mime.text import MIMEText
    msg.attach(MIMEText(text, 'plain', 'utf-8'))
    # The html section.
    if export:
        assert html is None
        content = lcg.Container(lcg.Parser().parse(text))
        exporter = lcg.HtmlExporter(translations=wiking.cfg.translation_path)
        node = lcg.ContentNode('mail', title=subject, content=content)
        context = exporter.context(node, lang)
        html = "<html>\n" + content.export(context) + "\n</html>\n"
    if html:
        msg.attach(MIMEText(html, 'html', 'utf-8'))
    # The attachment section.
    from email.mime.audio import MIMEAudio
    from email.mime.base import MIMEBase
    from email.mime.image import MIMEImage
    for a in attachments:
        file_name = os.path.basename(a.file_name())
        attin = a.stream()
        ctype = a.type()
        if ctype is None:
            ctype, encoding = mimetypes.guess_type(file_name)
            if ctype is None or encoding is not None:
                ctype = 'application/octet-stream'
        maintype, subtype = ctype.split('/', 1)
        if maintype == 'text':
            submsg = MIMEText(attin.read(), subtype, 'utf-8')
        elif maintype == 'image':
            submsg = MIMEImage(attin.read(), subtype)
        elif maintype == 'audio':
            submsg = MIMEAudio(attin.read(), subtype)
        else:
            submsg = MIMEBase(maintype, subtype)
            submsg.set_payload(attin.read())
            from email import encoders
            encoders.encode_base64(submsg)
        attin.close()
        submsg.add_header('Content-Disposition', 'attachment', filename=file_name)
        msg.attach(submsg)
    # Send the message.
    addr_list = [addr]
    if cc:
        addr_list += cc
    if not smtp_server:
        smtp_server = wiking.cfg.smtp_server or 'localhost'
    if not smtp_port:
        smtp_port = wiking.cfg.smtp_port or 25
    try:
        # Logging here is particularly useful to avoid confusion during development.
        # When smtp_server is not configured correctly, sendmail blocks waiting for
        # timeout.  This may look like nothing is happenning when watching the error
        # log during development (eg. when sending the bug report after
        # InternalServerError) while the request processing is not finished yet.
        log(OPR, "Sending mail to %s using %s:%s." % (addr, smtp_server, smtp_port))
        import smtplib
        server = smtplib.SMTP(smtp_server, smtp_port)
        try:
            server.sendmail(sender, addr_list, msg.as_string())
        finally:
            server.quit()
        return None
    except Exception as e:
        return str(e)


def validate_email_address(address, helo=None):
    """Validate given e-mail 'address'.

    The function performs some basic checks of the e-mail address validity,
    especially whether the given address is able to accept e-mail.  The check
    is not completely reliable, it may report the address as valid when it is
    not and under some uncommon conditions it may report a valid address as
    invalid.

    If the address is valid, the pair '(True, None,)' is returned.  If the
    address is invalid, the pair '(False, REASON,)' is returned, where 'REASON'
    is a string describing less or more accurately the reason why the address
    was not validated.

    If the 'hello' argument is not 'None', it is used as the identification of
    the connecting machine in the HELO SMTP command when checking availability
    of the address on remote sites.

    """
    assert isinstance(address, str)
    import dns.resolver
    import smtplib
    try:
        # We validate only common addresses, not pathological cases
        __, domain = address.split('@')
    except ValueError:
        return False, _("Invalid e-mail address format.")
    try:
        mxhosts = dns.resolver.query(domain, 'MX')
    except dns.resolver.NoAnswer:
        mxhosts = None
    except dns.resolver.NXDOMAIN:
        # Translators: Computer terminology. `gmail.com' is a domain name in email address
        # `joe@gmail.com'.
        return False, _("Domain not found.")
    except Exception as e:
        # Translators: Computer terminology.  Don't translate the acronym `DNS'.
        return False, _("Unable to retrieve DNS records: %s", str(e) or e.__class__.__name__)
    if mxhosts is None:
        try:
            ahosts = dns.resolver.query(domain, 'A')
        except dns.resolver.NoAnswer:
            return False, _("Domain not found.")
        except Exception as e:
            # Translators: Computer terminology.  Don't translate the acronym `DNS'.
            return False, _("Unable to retrieve DNS records: %s", str(e) or e.__class__.__name__)
        hosts = [h.to_text() for h in ahosts]
    else:
        hosts = [h.exchange.to_text() for h in mxhosts]
    if wiking.cfg.allow_smtp_email_validation:
        reasons = ''
        for host in hosts:
            if host[-1] == '.':
                host = host[:-1]
            try:
                smtp = smtplib.SMTP(host, local_hostname=helo)
                smtp.helo()
                code, message = smtp.mail('')
                if code >= 500:
                    raise Exception('SMTP command MAIL failed', code, message)
                code, message = smtp.rcpt(address)
                if code >= 500:
                    raise Exception('SMTP command RCPT failed', code, message)
                smtp.quit()
                break
            except Exception as e:
                if not (hasattr(e, 'errno') and e.errno == 421):
                    # Error 421 stands for Service temporarily unavailable.
                    # Skip such hosts without appending to reasons to be able
                    # to detect, that all servers were unavailable in the end.
                    reasons += ('%s: %s; ' % (host, e,))
        else:
            if reasons:
                return False, _("Invalid e-mail address: %s", reasons)
            else:
                return False, _("Unable to verify e-mail address: Mail servers for "
                                "'%s' are temporarily unavailable. The problem is "
                                "not on the side of this application and we can not "
                                "do anything about it. Please, try again later.")
    return True, None


_WKDAY = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun',)
_MONTH = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',)


def format_http_date(dt):
    """Return datetime as a str in the RFC 1123 format.

    Arguments:

      dt -- 'datetime.datetime' instance to be formatted.  It may be a timezone
        aware instance or a naive instance in UTC.

    """
    tz = dt.tzinfo
    if tz:
        # Convert a timezone aware datetime instance to a naive one in UTC.
        dt = dt.replace(tzinfo=None) - tz.utcoffset(dt)
    return '%s, %02d %s %04d %02d:%02d:%02d GMT' % (_WKDAY[dt.weekday()], dt.day,
                                                    _MONTH[dt.month - 1], dt.year,
                                                    dt.hour, dt.minute, dt.second)


def parse_http_date(date_string):
    """Return datetime corresponding to RFC 2616 date_string.

    Arguments:

      date_string -- string representing date and time in one of the
        formats supported by RFC 2616

    Returns corresponding 'datetime.datetime' instance in UTC or None when the
    date string doesn't match one of the expected formats.

    """
    date_string = date_string.strip()
    tz_offset = None
    # Remove weekday
    for d in _WKDAY:
        if date_string.startswith(d):
            date_string = date_string[len(d):].lstrip()
            if date_string.startswith(','):
                date_string = date_string[1:].lstrip()
            break
    if date_string[-3:] == 'GMT':
        # Remove GMT
        date_string = date_string[:-3].rstrip()
    elif date_string[-5] in ('+', '-') and date_string[-4:].isdigit():
        # Numeric timezone is not officially supported by RFC 2616, but is
        # sometimes used by user agents (for example in If-Modified-Since
        # header).
        tz_hours, tz_minutes = int(date_string[-4:-2]), int(date_string[-2:])
        if date_string[-5] == '-':
            tz_hours, tz_minutes = tz_hours * -1, tz_minutes * -1
        date_string = date_string[:-5].rstrip()
        tz_offset = datetime.timedelta(hours=tz_hours, minutes=tz_minutes)
    # Replace month name by a number
    for i, m in enumerate(_MONTH):
        pos = date_string.find(m)
        if pos >= 0:
            date_string = '%s%02d%s' % (date_string[:pos], i + 1, date_string[pos + 3:],)
            break
    # Parse the date
    for format_ in ('%d %m %Y %H:%M:%S', '%d-%m-%y %H:%M:%S', '%m %d %H:%M:%S %Y',):
        try:
            dt = datetime.datetime.strptime(date_string, format_)
        except ValueError:
            pass
        else:
            if tz_offset is not None:
                dt -= tz_offset
            return dt
    return None


def pdf_document(content, lang):
    """Return PDF document created from 'lcg_content'.

    Arguments:

      content -- document content, sequence of 'lcg.Content' or
        'lcg.ContentNode' instances
      lang -- document language as an ISO 639-1 Alpha-2 lowercase
        language code string or 'None'

    """
    assert isinstance(content, (list, tuple)), content
    assert all([isinstance(c, (lcg.Content, lcg.ContentNode)) for c in content])
    exporter = lcg.pdf.PDFExporter()
    children = []
    for i in range(len(content)):
        c = content[i]
        if not isinstance(c, lcg.ContentNode):
            c = lcg.ContentNode(id='wiking%d' % (i,), title=' ', content=c)
        children.append(c)
    lcg_content = lcg.ContentNode(id='__dummy', content=lcg.Content(), children=children)
    context = exporter.context(lcg_content, lang)
    pdf = exporter.export(context)
    return pdf


def generate_random_string(length):
    """Return a random string of given length."""
    # import base64
    try:
        code = ''.join(['%02x' % byte for byte in os.urandom(length // 2 + 1)])
    except NotImplementedError:
        import random
        random.seed()
        code = ''.join(['%02x' % random.randint(0, 255) for i in range(length // 2 + 1)])
    return code[:length]


def test_generate_random_string():
    for length in (1, 2, 8, 9, 10, 28, 32, 33):
        string = generate_random_string(length)
        assert len(string) == length
        string2 = generate_random_string(length)
        assert string != string2


_pdb = None

def breakpoint():
    """Insert a breakpoing at given position and start PDB if not already running.

    Starts a PDB session if one was not started previously and inserts a
    breakpoint.  The debugger can be accessed by telnet on localhost, port
    4444.

    """
    global _pdb
    if not _pdb:
        from remote_pdb import RemotePdb
        _pdb = RemotePdb('127.0.0.1', 4444)
    _pdb.set_trace()
