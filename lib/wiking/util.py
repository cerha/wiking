# Copyright (C) 2006, 2007, 2008, 2009, 2010, 2011, 2012 Brailcom, o.p.s.
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

import lcg, pytis, pytis.presentation
import sys, httplib, collections, datetime
from xml.sax import saxutils

DBG = pytis.util.DEBUG
EVT = pytis.util.EVENT
OPR = pytis.util.OPERATIONAL
log = pytis.util.StreamLogger(sys.stderr).log

_ = lcg.TranslatableTextFactory('wiking')

from wiking import *


class RequestError(Exception):
    """Base class for predefined error states within request handling.

    Exceptions of this class represent unexpected situations in request
    handling.  They typically don't represent an error in the application, but
    rater an invalid state in request processing, such as unauthorized access,
    request for an invalid URI etc.  Such errors are normally handled by
    displaying an error message within the content part of the page.  The
    overall page layout, including navigation and other static page content is
    displayed as on any other page.  Most error types are not logged neither
    emailed, since they are caused by an invalid request, not a bug in the
    application.

    The Wiking handler is responsible for handling these errors approprietly.
    This usually means to output a page with title and body content as returned
    by the methods 'title()' and 'message()' and setting the HTTP response
    status code according to 'status_code()'.

    This class is abstract.  The error code and error message must be defined
    by a derived class.  The error message may also require certain constructor
    arguments passed when raising the error.

    """
    _TITLE = None
    
    _STATUS_CODE = httplib.OK
    """Relevant HTTP status code.

    The code may be 200 (OK) for errors which don't map to HTTP errors.

    """
    _LOG = True
    """Indicates whether this kind of error should be logged on the server.

    This attribute is True by default, but some derived classes may set it to
    False if logging is not appropriate for given error type.

    """
    _LOG_FORMAT = "%(error)s: %(server_hostname)s%(uri)s [%(user)s@%(remote_host)s]"
    """Python format string used for printing error message to the system log.
    
    The format string may use the following format variables:
       error -- error class name string (the class derived from 'RequestError'),
       server_hostname -- requested server host name (virtual host),
       uri -- URI of the request,
       user -- current user's login name ('User.login()') or 'anonymous' when
         user is not logged,
       remote_host -- IP adress of the client's host as a string,
       referrer -- HTTP referer (URI of the page linking to this request's
         URI),
       user_agent -- client software identification from the 'User-Agent' HTTP
         header,
       server_software -- server software identification (current versions of
         Wiking, LCG and Pytis)
    
    """
    # TODO: The 'req' object should be required as constructor argument and
    # avoided in all public methods.  This change requires changes in
    # applications, so it must be done carefully...

    def __init__(self, *args, **kwargs):
        import inspect
        # Ignore this frame and few last frames (they are inside mod_python).
        self._stack = reversed(inspect.stack()[1:-4])
        self._already_logged = False
        super(RequestError, self).__init__(*args, **kwargs)
    
    def title(self, req):
        if self._TITLE is not None:
            return self._TITLE
        else:
            code = self.status_code(req)
            name = " ".join(pp.split_camel_case(self.__class__.__name__))
            if code == httplib.OK:
                return name
            else:
                # Translators: '%(code)d' is replaced by error number and '%(name)s' by error title.
                return _("Error %(code)d: %(name)s", code=code, name=name)

    def message(self, req):
        """Return the error message as an 'lcg.Content' element structure.""" 
        return None

    def status_code(self, req):
        """Return the HTTP response status code corresponding to this request error.

        The code is 200 (OK) for errors which don't map to HTTP errors.

        """
        return self._STATUS_CODE
        
    def log(self, req):
        """Currently used only for debugging, but in future it should be used for proper logging."""
        # Prevent double logging when handling exception in exception (see handler.py).
        import wiking
        if self._LOG and not self._already_logged:
            message = self._LOG_FORMAT % dict(
                error=self.__class__.__name__,
                server_hostname = req.server_hostname(),
                uri=req.uri(),
                user=(req.user() and req.user().login() or 'anonymous'),
                remote_host=req.remote_host(),
                referrer=req.header('Referer'),
                user_agent=req.header('User-Agent'),
                server_software='Wiking %s, LCG %s, Pytis %s' % \
                    (wiking.__version__, lcg.__version__, pytis.__version__))
            if wiking.cfg.debug:
                frames = ['%s:%d:%s()' % tuple(frame[1:4]) for frame in self._stack]
                message += " (%s)" % ", ".join(frames)
            log(OPR, message)


class AuthenticationError(RequestError):
    """Error indicating that authentication is required for the resource."""
    
    # Translators: This is a warning on a webpage which is only accessible for logged in users
    _TITLE = _("Authentication required")
    _HTTP_AUTH_MATCHER = re.compile('.*(Thunderbird|Icedove|Liferea)/.*')
    """Regular expression matching user agents for which HTTP authentication is used automatically.

    HTTP authentication is normally requested by client through the special
    request argument '__http_auth'.  But sometimes it is more practical to
    avoid such argument in the URL.  For example we want to publish a URL of an
    RSS channel.  Some RSS readers do support cookie based authentication and
    we don't want to force them to use HTTP authentication for its lack of
    logout possibility and other drawbacks.  However, other RSS readers don't
    support cookie based authentication and we don't want to publish two
    distinct URLs and explain which to choose in which case.  Thus we are a
    little brave and guess the appropriate authentication method from the User
    Agent header.

    The currently recognized user agents are Thunderbird mail reader (for its
    built in RSS support) and Liferea.
    
    """
    _LOG = False
    
    def status_code(self, req):
        """Return authentication error page status code.

        If HTTP authentication is active (either requested explicitly or turned
        on automatically -- see '_HTTP_AUTH_MATCHER'), the status code 401
        (UNAUTHORIZED) is returned, otherwise the code is 200 (OK)
        and cookie based authentication mechanism will be used.
        
        """
        agent = req.header('User-Agent')
        if wiking.cfg.allow_http_authentication and \
                (req.param('__http_auth') or
                 agent is None or self._HTTP_AUTH_MATCHER.match(agent)):
            # Ask for HTTP Basic authentication.
            return httplib.UNAUTHORIZED
        else:
            return httplib.OK

    def message(self, req):
        return LoginDialog(self.args and self.args[0] or None)


class AuthenticationRedirect(AuthenticationError):
    """Has the same effect as AuthenticationError, but is just not an error."""
    
    # Translators: Login dialog page title (use a noun).
    _TITLE = _("Login")


class DisplayDocument(Exception):
    """Exception that should result in displaying the given document."""
    def __init__(self, document):
        """
        Arguments:

          document -- document to display

        """
        self._document = document
        super(DisplayDocument, self).__init__()

    def document(self):
        return self._document


class Abort(RequestError):
    """Error useful for aborting regular request processing and displaying substitutional content.

    Raising this error leads to displaying arbitrary substitutional content (such as a
    'ConfirmationDialog' instance).

    The constructor must be called with two arguments:
      title -- dialog title as a (translatable) string
      content -- dialog content as an 'lcg.Content' instance or a sequence of such instances

    """
    _LOG = False

    def title(self, req):
        return self.args[0]

    def message(self, req):
        return self.args[1]


class PasswordExpirationError(RequestError):
    
    _TITLE = _("Your password expired")
    
    def message(self, req):
        content = lcg.p(_("Your password expired.  Access to the application is now blocked for "
                          "security reasons until you change your password."))
        uri = wiking.module('Application').password_change_uri(req)
        if uri:
            # Translators: This is a link on a webpage
            content = (content, lcg.p(lcg.link(uri, _("Change your password"))))
        return content

    
class AuthorizationError(RequestError):
    """Error indicating that the user doesn't have privilegs for the action."""
    
    # Translators: An error message
    _TITLE = _("Access Denied")

    def message(self, req):
        return (lcg.p(_("You don't have sufficient privilegs for this action.")),
                lcg.p(_("If you are sure that you are logged in under the right account "
                        "and you believe that this is a problem of access rights assignment, "
                        "please contact the administrator at %s.", wiking.cfg.webmaster_address),
                      formatted=True))

class DecryptionError(RequestError):
    """Error signalling that a decryption key is missing.

    Its argument is the name of the inaccessible encryption area.
    
    """
    def message(self, req):
        return DecryptionDialog(self.args[0])
    
class BadRequest(RequestError):
    """Error indicating invalid request argument values or their combination.

    Wiking applications usually ignore request arguments which they don't
    recognize.  This error is mostly usefull in situations, where the required
    arguments are missing or contain invalid values or their combinations.

    More precise error description may be optionally passed as constructor
    argument.  This message will be printed into user's browser window.  If
    no argument is passed, the default message `Invalid request arguments.'
    is printed.  If more arguments are passed, each message is printed as
    separate paragraph. 

    """
    _STATUS_CODE = httplib.BAD_REQUEST
    
    def message(self, req):
        if self.args:
            return lcg.coerce([lcg.p(arg) for arg in self.args])
        else:
            return lcg.p(_("Invalid request arguments."))

        
class NotFound(RequestError):
    """Error indicating invalid request target."""
    _STATUS_CODE = httplib.NOT_FOUND
    
    def message(self, req):
        # Translators: The word 'item' is intentionaly very generic, since it may mean a page,
        # image, streaming video, RSS channel or anything else.
        return (lcg.p(_("The item '%s' does not exist on this server or cannot be served.",
                        req.uri())),
                lcg.p(_("If you are sure the web address is correct, but are encountering "
                        "this error, please contact the administrator at %s.",
                        wiking.cfg.webmaster_address),
                      formatted=True))
    #return lcg.coerce([lcg.p(p) for p in msg])

    
class Forbidden(RequestError):
    """Error indicating unavailable request target."""
    _STATUS_CODE = httplib.FORBIDDEN
    
    def message(self, req):
        return (lcg.p(_("The item '%s' is not available.", req.uri())),
                lcg.p(_("The item exists on the server, but can not be accessed.")))

    
class NotAcceptable(RequestError):
    """Error indicating unavailability of the resource in the requested language.

    Constructor may be called with a sequence of language codes as its first argument.  This
    sequence denotes the list of available language variants of the requested
    page/document/resource.

    """
    # Translators: Title of a dialog on a webpage
    _TITLE = _("Language selection")
    _STATUS_CODE = httplib.NOT_ACCEPTABLE
    
    def message(self, req):
        msg = (lcg.p(_("The resource '%s' is not available in either of the requested languages.",
                       req.uri())),)
        if self.args:
            # Translators: Meaning language variants. A selection of links to various language
            # versions follows.
            msg += (lcg.p(_("The available variants are:")),
                    lcg.ul([lcg.link("%s?setlang=%s" % (req.uri(), l),
                                     label=lcg.language_name(l) or l)
                            for l in self.args[0]]))
        msg += (lcg.HorizontalSeparator(),
                lcg.p(_("Your browser is configured to accept only the following languages:")),
                lcg.ul([lcg.language_name(l) or l for l in req.preferred_languages()]),
                lcg.p(_("If you want to accept other languages permanently, setup the language "
                        "preferences in your browser or contact your system administrator.")))
        return msg


class InternalServerError(RequestError):
    """General error in application -- error message is required as an argument."""
    _TITLE = _("Internal Server Error")
    _STATUS_CODE = httplib.INTERNAL_SERVER_ERROR

    # Avoid logging of this errror as it is now done in
    # 'Application.handle_exception()'.  It would probably make sense to move
    # logging here from there completely, but this change would require some
    # extra work and thought.
    _LOG = False

    def __init__(self, message, einfo=None):
        self._message = message
        self._einfo = einfo
        super(InternalServerError, self).__init__()
    
    def message(self, req):
        # TODO: Even though the admin address is in a formatted paragraph, it is not formatted as a
        # link during internal server error export.  It works well in all other cases.
        if self._einfo and wiking.cfg.debug:
            import cgitb
            return HtmlContent(cgitb.html(self._einfo))
        else:
            return (lcg.p(_("The server was unable to complete your request.")),
                    lcg.p(_("Please inform the server administrator, %s if the problem "
                            "persists.", wiking.cfg.webmaster_address), formatted=True),
                    lcg.p(_("The error message was:")),
                    lcg.PreformattedText(self._message))
    
        
class ServiceUnavailable(RequestError):
    """Error indicating a temporary problem, which may not appaper in further requests."""
    _TITLE = _("Service Unavailable")
    _STATUS_CODE = httplib.SERVICE_UNAVAILABLE
    
    def message(self, req):
        return (lcg.p(_("The requested function is currently unavailable. "
                        "Try repeating your request later.")),
                lcg.p(_("Please inform the server administrator, %s if the problem "
                        "persists.", wiking.cfg.webmaster_address), formatted=True))
    
    
class MaintenanceModeError(ServiceUnavailable):
    """Error indicating an invalid action in maintenance mode.

    The maintenance mode can be turned on by the 'maintenance' configuration option.  If this
    option is set to 'true', no database access will be allowed and any attempt to do so will raise
    this error.  The application should handle all these errors gracefully to support the
    mainenance mode.
    
    """
    _TITLE = _("Maintenance Mode")
    _LOG = False

    def message(self, req):
        # Translators: Meaning that the system (webpage) does not work now because we are
        # updating/fixing something but will work again after the maintaince is finished.
        return lcg.p(_("The system is temporarily down for maintenance."))


class Redirect(Exception):
    """Exception class for HTTP redirection.

    Raising an exception of this class at any point of Wiking request
    processing will lead to HTTP redirection to the URI given to the exception
    instance constructor.  Wiking handler will automatically send the correct
    redirection response to the client (setting the appropriate HTTP headers
    and return codes).

    This class results in temporary redirection.  See 'PermanentRedirect' if
    you need a permanent redirection.

    """
    _PERMANENT = False
    
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

    def permanent(self):
        """Return true if the redirection is permanent according to HTTP specification."""
        return self._PERMANENT

    
class PermanentRedirect(Redirect):
    """Exception class for permanent HTTP redirection.

    Same as the parent class, but results in permanent redirection according to
    HTTP specification.
    
    """
    _PERMANENT = True

# ============================================================================

class Theme(object):

    class Color(object):
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
        Color('inactive-folder'),
        Color('meta-fg', inherit='foreground'),
        Color('meta-bg', inherit='background'),
        )

    _DEFAULTS = {'foreground': '#000',
                 'background': '#fff',
                 'border': '#bcd',
                 'heading-bg': '#d8e0f0',
                 'heading-line': '#ccc',
                 'frame-bg': '#eee',
                 'frame-border': '#ddd',
                 'link': '#03b',
                 'link-hover': '#d60',
                 'meta-fg': '#840',
                 'help': '#444',
                 'error-bg': '#fdb',
                 'error-border': '#fba',
                 'message-bg': '#cfc',
                 'message-border': '#aea',
                 'table-cell': '#f8fafb',
                 'table-cell2': '#f1f3f2',
                 'top-bg': '#efebe7',
                 'top-border': '#9ab',
                 'highlight-bg': '#fc8',
                 'inactive-folder': '#d2d8e0',
                 }

    def __init__(self, colors=None):
        if not colors:
            colors = self._DEFAULTS
        self._colors = dict([(c.id(), c) for c in self.COLORS])
        self._theme = {'color': dict([(key, self._color(key, colors))
                                      for key in self._colors.keys()])}
        
    def _color(self, key, colors):
        if key in colors:
            return colors[key]
        else:
            inherit = self._colors[key].inherit()
            if inherit:
                return self._color(inherit, colors)
            elif colors != self._DEFAULTS:
                return self._color(key, self._DEFAULTS)
            else:
                return 'inherit'
        
    def __getitem__(self, key):
        return self._theme[key]
    
        
class MenuItem(object):
    """Abstract menu item representation."""
    def __init__(self, id, title, descr=None, submenu=(), hidden=False, active=True,
                 foldable=False, order=None, variants=None):
        """Arguments:

          id -- unique menu item identifier.  
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
        submenu = list(submenu)
        submenu.sort(key=lambda i: i.order())
        self._submenu = submenu
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


class Panel(object):
    """Panel representation to be passed to 'Document.build()'.

    Panels are small applet windows displayed by the right side of the page (in
    the default style).  They can hold arbitrary content defined by the
    application and optionally link to RSS channels.

    """
    def __init__(self, id, title, content, accessible_title=None, channel=None):
        """
        @type id: basestring
        @param id: Panel unique identifier.  This identifier is included in
        the output and thus may be used for panel specific styling.
        
        @type title: basestring
        @param title: Title displayed in panel heading.
        
        @type content: L{lcg.Content}
        @param content: Content displayed within the panel area.
        
        @type accessible_title: basestring
        @param accessible_title: Panel title for assistive technologies or
        None.  Panel is by default represented by its 'title' to assistive
        technologies.  If you need to use a more descriptive title for this
        purpose than it is desirable to display in panel heading, use this
        argument to pass an alternative title.

        @type channel: basestring
        @param channel: RSS channel URI if this panel represents an RSS
        channel.  If not None, the panel will indicate a channel icon with a
        link to the channel.  Channels of all panels present on a page will
        also be automatically included in <link> tags within the page header.
        
        """
        assert isinstance(id, basestring), id
        assert isinstance(title, basestring), title
        assert isinstance(content, lcg.Content), content
        assert accessible_title is None or isinstance(accessible_title, basestring), \
            accessible_title
        assert channel is None or isinstance(channel, basestring), channel
        self._id = id
        self._title = title
        self._content = content
        self._accessible_title = accessible_title or title
        self._channel = channel
        
    def id(self):
        return self._id
    
    def title(self):
        return self._title
    
    def accessible_title(self):
        return self._accessible_title

    # TODO: navigable ....
    
    def content(self):
        return self._content

    def channel(self):
        return self._channel


class LoginPanel(Panel):
    """Displays login/logout controls and other relevant information."""
    
    class PanelContent(lcg.Content):
        def export(self, context):
            g = context.generator()
            req = context.req()
            user = req.user()
            result = LoginCtrl().export(context)
            appl = wiking.module('Application')
            if user:
                if wiking.cfg.display_role_in_login_panel:
                    # TODO: show only explicitly assigned roles, not special
                    # roles, such as wiking.Roles.AUTHENTICATED.  Also for
                    # compound roles, show only the top level role.  This
                    # information is, however, currnetly not available.
                    role_names = [role.name() for role in user.roles()]
                    if role_names:
                        result += g.br() + '\n' + lcg.concat(role_names, separator=', ')
                expiration = user.password_expiration()
                if expiration:
                    import datetime
                    if datetime.date.today() >= expiration:
                        # Translators: Information text on login panel.
                        result += g.br() +'\n'+ _("Your password expired")
                    else:
                        date = lcg.LocalizableDateTime(str(expiration))
                        # Translators: Login panel info. '%(date)s' is replaced by a concrete date.
                        result += g.br() +'\n'+ _("Your password expires on %(date)s", date=date)
                uri = appl.password_change_uri(req)
                if uri:
                    # Translators: Link on login panel on the webpage.
                    result += g.br() +'\n'+ g.link(_("Change your password"), uri)
            else:
                uri = appl.registration_uri(req)
                if uri:
                    # Translators: Login panel/dialog registration link.  Registration allows the
                    # user to obtain access to the website/application by submitting his personal
                    # details.
                    result += g.br() +'\n'+ g.link(_("New user registration"), uri)
            added_content = appl.login_panel_content(req)
            if added_content:
                exported = lcg.coerce(added_content).export(context)
                result += '\n'+ g.div(exported, cls='login-panel-content')
            return result
        
    def __init__(self):
        super(LoginPanel, self).__init__('login', _("Login"), self.PanelContent(),
                                         accessible_title=_("Login Panel"))
        

class Document(object):
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
                 variants=None, resources=(), globals=None, layout=None):
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
          variants -- available language variants as a sequence of language
            codes.  Should be defined if only a limited set of target languages
            for the document exist.  For example when the document is read form
            a file or a database and it is known which other versions of the
            source exist.  If None, variants default to the variants defined by
            the corresponding menu item (if found) or to application-wide set
            of all available languages.
          resources -- external resources available for this document as a
            sequence of 'lcg.Resource' instances.
          layout -- output layout as one of `wiking.Exporter.Layout' constants
            or None for the default layout.

        """
        self._title = title
        self._subtitle = subtitle
        self._content = content
        self._lang = lang
        self._sec_lang = sec_lang
        self._variants = variants
        self._resources = tuple(resources)
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

    def resources(self):
        """Return the 'resources' passed to the constructor."""
        return self._resources
        
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


class Response(object):
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
                 status_code=httplib.OK, filename=None, headers=()):
        """Arguments:
        
          data -- respnse data as one of the types described below.
          
          content_type -- The value to be used for the 'Content-Type' HTTP
            header (basestring).  When 'data' is a unicode instance, and
            'content_type' is one of "text/html", "application/xml", "text/css"
            and "text/plain", the charset information is appended automatically
            to the value.  So for example "text/plain" will be converted to
            "text/plain; charset=UTF-8".

          content_length -- Explicit value for the 'Content-Length' HTTP header
            (basestring).  Set automatically when 'data' is 'str', 'buffer' or
            'unicode', but should be supplied when 'data' is an iterable
            object.
            
          status_code -- integer number denoting the HTTP response status code
            (default is 'httplib.OK').  It is recommended to use 'httplib'
            constants for the status codes.

          filename -- file name (basestring) for the 'Content-disposition' HTTP
            header.  This has the same effect as adding a pair
            ('Content-disposition', "attachment; filename=<filename>" to
            'headers'.  The browser will usually show a "Save File" dialog and
            suggest given file name as the default name for saving the request
            result into a file.

          headers -- any additional HTTP headers to be sent with the request as
            a sequence of pairs NAME, VALUE (strings).

        The supported response data types:
          str -- is sent unchanged to the client
          buffer -- is converted to str
          unicode -- is encoded to str using the current request encoding
          iterable -- iterable object (typically a generator) returning
            response data in chunks.  The returned chunks must be strings.
          
        """
        self._data = data
        self._content_type = content_type
        self._content_length = content_length
        self._status_code = status_code
        self._headers = headers
        self._filename = filename
        
    def data(self):
        return self._data

    def content_type(self):
        return self._content_type

    def content_length(self):
        return self._content_length

    def status_code(self):
        return self._status_code

    def headers(self):
        return self._headers
    
    def filename(self):
        return self._filename
        
    
    
class BoundCache(object):
    """Simple unlimited cache caching only in a limited scope.

    The scope can be passed as an arbitrary Python object and the cache is automatically reset if
    the scope is different than the previously used scope.

    """
    def __init__(self):
        self._scope = None
        self._cache = {}
    
    def get(self, scope, key, func):
        """Get the cached value for 'key'.

        Use 'func' to retrieve the value if it is not in the cache.  Reset the cache if the 'scope'
        is not the same object (in the sense of Python identity) as passed in the previous call to
        this method.
        
        """
        if self._scope is not scope:
            self._cache = {}
            self._scope = scope
        try:
            result = self._cache[key]
        except KeyError:
            result = self._cache[key] = func()
        return result


class Channel(object):
    """RSS channel specification."""
    def __init__(self, id, title, descr, content, limit=None, sorting=None, condition=None,
                 webmaster=None):
        """
        @type id: basestring
        @param id: Channel identifier unique within one module's channels.  The
        identifier is used as a part of channel URL, so it should not contain
        special characters.
        
        @type title: basestring
        @param title: Channel title
        
        @type descr: basestring
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
        
        @type webmaster: basestring
        @param webmaster: Channel webmaster e-mail address.  If None,
        'wiking.cfg.webmaster_address' is used.

        """
        assert isinstance(id, basestring)
        assert isinstance(title, basestring)
        assert isinstance(descr, basestring)
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
    

class ChannelContent(object):
    """Defines how PytisModule records map to RSS channel items.

    Used for 'Channel' 'content' constructor argument.

    The constructor arguments correspond to the supported channel item
    fields and given values define how to get the field value from the
    module's record.  Each value is either string, function (callable
    object) or None.  In case of a string, the field value is taken
    directly from the record's exported field value of the same name.  A
    callable object allows more flexibility.  Given function is called with
    two arguments ('req' and 'record') and the returned value is used
    directly.  The function must return a string, unicode,
    L{lcg.TranslatableText} or None.  If the specification value is None or
    if the resulting field value is None, the field is not included in the
    output or a default value is used (as documented for each field).

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
        assert isinstance(title, str) or isinstance(title, collections.Callable), title
        assert link is None or isinstance(link, str) or isinstance(link, collections.Callable), link
        assert descr is None or isinstance(descr, str) or isinstance(descr, collections.Callable), descr
        assert date is None or isinstance(date, str) or isinstance(date, collections.Callable), date
        assert author is None or isinstance(author, str) or isinstance(author, collections.Callable), author
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

    
class RssWriter(object):
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


# ============================================================================
# Classes derived from LCG components
# ============================================================================

class WikingNode(lcg.ContentNode):

    def __init__(self, id, page_heading=None, panels=(), lang=None, sec_lang=None,
                 active=True, foldable=False, layout=None, **kwargs):
        super(WikingNode, self).__init__(id, **kwargs)
        self._page_heading = page_heading
        self._panels = panels
        self._lang = lang
        self._sec_lang = sec_lang
        self._active = active
        self._foldable = foldable
        self._layout = layout
        for panel in panels:
            panel.content().set_parent(self)

    def add_child(self, node):
        if isinstance(self._children, tuple):
            self._children = list(self._children)
        node._set_parent(self)
        self._children.append(node)
        
    def lang(self):
        return self._lang

    def sec_lang(self):
        return self._sec_lang

    def active(self):
        return self._active

    def foldable(self):
        return self._foldable
    
    def page_heading(self):
        return self._page_heading or self._title
    
    def top(self):
        parent = self._parent
        if parent is None:
            return None
        elif parent.parent() is None:
            return self
        else:
            return parent.top()
    
    def panels(self):
        return self._panels

    def layout(self):
        return self._layout

    
class PanelItem(lcg.Content):

    def __init__(self, fields):
        super(PanelItem, self).__init__()
        self._fields = fields
        
    def export(self, context):
        g = context.generator()
        items = [g.span(uri and g.link(value, uri) or value,
                            cls="panel-field-"+id)
                 for id, value, uri in self._fields]
        return g.div(items, cls="item")


class LoginCtrl(lcg.Content):
    """Displays current logged in user and login/logout link/button."""
    def __init__(self, inline=False):
        super(LoginCtrl, self).__init__()
        self._inline = inline
        
    def export(self, context):
        g = context.generator()
        req = context.req()
        user = req.user()
        target_uri = req.uri()
        if user:
            username = user.name()
            uri = user.uri()
            if uri:
                username = g.link(username, uri, title=_("Go to your profile"))
            # Translators: Logout button label (verb in imperative).
            cmd, label = ('logout', _("log out"))
        else:
            # Translators: Login status info.  If logged, the username is displayed instead. 
            username = _("not logged")
            # Translators: Login button label (verb in imperative).
            cmd, label = ('login', _("log in"))
            if req.uri().endswith('_registration'):
                target_uri = '/' # Redirect logins from the registration forms to site root
        link = g.link(label, g.uri(target_uri, command=cmd), cls='login-ctrl')
        if self._inline:
            link = '[' + link + ']'
        else:
            link = g.span('[', cls="hidden") + link + g.span(']',cls="hidden")
        result = username + ' ' + link
        if self._inline:
            # Translators: Login info label (noun) followed by login name and other info.
            result = _("Login") + ': ' + result
        return result


class LoginDialog(lcg.Content):
    """Login dialog for entering login name and password."""
    def __init__(self, message=None):
        assert message is None or isinstance(message, basestring)
        self._message = message
        super(LoginDialog, self).__init__()
        
    def export(self, context):
        g = context.generator()
        req = context.req()
        credentials = req.credentials()
        if credentials:
            login = credentials[0]
        else:
            login = None
        def hidden_field(param, value):
            if isinstance(value, basestring):
                return g.hidden(name=param, value=value)
            elif isinstance(value, (tuple, list)):
                return lcg.concat([hidden_field(param, v) for v in value], separator="\n")
            else:
                # This may be a file field, or anything else?
                # TODO: Is it a good idea to leave the field out without a warning?
                return ''
        hidden = [hidden_field(param, req.param(param)) for param in req.params()
                  if param not in ('command', 'login', 'password', '__log_in')]
        content = (
            g.label(_("Login name")+':', id='login') + g.br(),
            g.field(name='login', value=login, id='login', size=18, maxlength=64),
            g.br(), 
            g.label(_("Password")+':', id='password') + g.br(),
            g.field(name='password', id='password', password=True, size=18, maxlength=32),
            g.br(),
            g.hidden(name='__log_in', value='1'),
            ) + tuple(hidden) + (
            # Translators: Login button label - verb in imperative.
            g.submit(_("Log in"), cls='submit'),)
        appl = wiking.module('Application')
        links = [g.link(label, uri) for label, uri in
                 # Translators: Webpage link leading to registration form.
                 ((_("New user registration"), appl.registration_uri(req)),
                 # Translators: Login dialog link to password change or password reminder (depends
                 # on configuration).
                  (_("Forgot your password?"), appl.password_reminder_uri(req))) if uri]
        if links:
            content += (g.list(links),)
        if not req.https() and wiking.cfg.force_https_login:
            uri = req.server_uri(force_https=True) + req.uri()
        else:
            uri = req.uri()
        result = (self._message and g.div(g.escape(self._message), cls='errors') or '') + \
                 g.form(content, method='POST', action=uri, name='login_form', cls='login-form') +\
                 g.script("onload_ = window.onload; window.onload = function() { "
                          "if (onload_) onload_(); "
                          "setTimeout(function () { document.login_form.login.focus() }, 0); };")
        added_content = appl.login_dialog_content(req)
        if added_content:
            exported = lcg.coerce(added_content).export(context)
            result += "\n" + g.div(exported, cls='login-dialog-content')
        return result


class DecryptionDialog(lcg.Content):
    """Password dialog for entering a decryption password."""
    def __init__(self, name):
        assert isinstance(name, basestring)
        self._decryption_name = name
        super(DecryptionDialog, self).__init__()
        
    def export(self, context):
        g = context.generator()
        req = context.req()
        # Translators: Web form label and message
        message = _("Decryption password for '%s'", self._decryption_name)
        content = (
            g.label(message+':', id='__decryption_password') + g.br(),
            g.field(name='__decryption_password', id='__decryption_password', password=True,
                    size=18, maxlength=32),
            g.br(),
            # Translators: Web form button.
            g.submit(_("Send password"), cls='submit'),)
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
                      g.form(g.submit(_("Continue")),
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

class HtmlRenderer(lcg.Content):
    """LCG content class for wrapping a direct HTML renderer function.

    This is a simple convenience wrapper for situations where HTML content is
    rendered directly by a Python function passed to the constructor.  The
    result can be placed within an LCG content hierarchy and the passed
    renderer function will be called on export with at least three arguments
    (element, context, generator), where 'element' is the 'HtmlRenderer'
    instance, 'context' is a 'wiking.Exporter.Context' instance and 'generator'
    is an 'lcg.HtmlGenerator' instance.  Also any additional arguments
    (including keyword arguments) passed to the constructor are passed on.

    Use with caution.  Defining specific content classes for more generic
    content elements is encouraged over using this class.  This class should
    only be used for simple cases where defining a class makes too much
    unnecessary noise...

    """
    def __init__(self, renderer, *args, **kwargs):
        """Arguments:

        renderer -- the rendering function (see class docstring for details).
        *args, **kwargs -- all remaining arguments are passed along to
          'renderer' when called on export.

        """
        assert isinstance(renderer, collections.Callable)
        self._renderer = renderer
        self._renderer_args = args
        self._renderer_kwargs = kwargs
        super(HtmlRenderer, self).__init__()
    
    def export(self, context):
        return self._renderer(self, context, context.generator(),
                              *self._renderer_args, **self._renderer_kwargs)
    
class IFrame(lcg.Content):
    """HTML specific IFRAME component."""
    def __init__(self, uri, width=400, height=200):
        self._uri = uri
        self._width = width
        self._height = height
        super(IFrame, self).__init__()
        
    def export(self, context):
        return context.generator().iframe(self._uri, width=self._width, height=self._height)


class Notebook(lcg.Container):
    """HTML Notebook widget as an LCG content element.

    This widget is currently used for 'PytisModule' bindings.  Each binding
    side form is displayed as a separate tab.  This widget is quite generic so
    it could have been defined in LCG itself, but its export is HTML specific
    and the user interface relies on Wiking specific JavaScript code in
    'wiking.js'.

    The notebook tabs are represented by 'lcg.Section' instances.  The sections
    define tab titles, descriptions and content.  This makes the notebook
    degrade gracefully in non-javascript browsers and possibly also in other
    output formats.

    """
    def __init__(self, content, active=None, **kwargs):
        """Arguments:

           content -- sequence of 'lcg.Section' instances representing the tabs
           active -- id (anchor name) of the active tab or None
           **kwargs -- other arguments defined by the parent class
           
        """
        self._active = active
        super(Notebook, self).__init__(content, **kwargs)
    
    def name(self):
        # Avoid creation of the inner div (the name is present in outer div's cls).
        return None
    
    def export(self, context):
        g = context.generator()
        id = 'notebook-%x' % lcg.positive_id(self)
        switcher = g.ul(lcg.concat([g.li(g.a(s.title(), href='#'+s.anchor(), title=s.descr(),
                                             cls=(s.anchor()==self._active and 'current' or None)),
                                         cls="notebook-tab")
                                    for s in self.sections(context)]),
                        cls='notebook-switcher')
        return (g.div(switcher + super(Notebook, self).export(context), id=id,
                      cls=' '.join([x for x in ('notebook-container', self._name) if x])) +
                g.script(g.js_call('new wiking.Notebook', id)))

    
# ============================================================================
# Classes derived from Pytis components
# ============================================================================

class FieldSet(pp.GroupSpec):
    """Deprecated: Use pytis.presentation.FieldSet instead."""
    def __init__(self, label, fields, horizontal=False):
        orientation = horizontal and pp.Orientation.HORIZONTAL or pp.Orientation.VERTICAL
        super(FieldSet, self).__init__(fields, label=label, orientation=orientation)

        
from pytis.data.dbapi import DBAPIData
    
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

    _dbfunction = {} # DBFunftion* instance cache

    def __init__(self, *args, **kwargs):
        super(WikingDefaultDataClass, self).__init__(*args, **kwargs)
        # We don't want to care how `connection_data' is stored in the parent class...
        self._dbconnection = kwargs['connection_data'].select(kwargs.get('connection_name'))

    def _row_data(self, **kwargs):
        return [(k, pd.Value(self.find_column(k).type(), v)) for k, v in kwargs.items()]
    
    def get_rows(self, skip=None, limit=None, sorting=(), condition=None, arguments=None,
                 columns=None, transaction=None, **kwargs):
        if kwargs:
            conds = [pd.EQ(k,v) for k,v in self._row_data(**kwargs)]
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
                row = self.fetchone(transaction=transaction)
                if row is None:
                    break
                rows.append(row)
                if limit is not None and len(rows) > limit:
                    break
        finally:
            try:
                self.close()
            except:
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

    def dbfunction(self, name, *args):
        """DEPRECATED.  Use PytisModule._call_db_function() instead."""
        # Used in some applications (solas).
        try:
            function = self.__class__._dbfunction[name]
        except KeyError:
            function = self.__class__._dbfunction[name] = \
                       pytis.data.DBFunctionDefault(name, self._dbconnection)
        result = function.call(pytis.data.Row(args))
        return result[0][0].value()


class Specification(pp.Specification):
    help = None # Default value needed by CMSModule.descr()
    actions = []
    data_cls = WikingDefaultDataClass

    def __init__(self, wiking_module):
        self._module = wiking_module
        if self.table is None:
            self.table = pytis.util.camel_case_to_lower(wiking_module.name(), '_')
        actions = self.actions
        if isinstance(actions, collections.Callable):
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
            from 'pytis.web.BrowseForm'.
          enabled -- function of one argument ('pp.PresentedRow' instance) determining whether this
            binding is relevant for given row of the related main form.  If the function returns
            'True', the binding is used, otherwise it is omitted.

        Other arguments are same as in the parent class.
            
        """
        form = kwargs.pop('form', None)
        enabled = kwargs.pop('enabled', None)
        super(Binding, self).__init__(*args, **kwargs)
        if isinstance(form, tuple):
            form_cls, form_kwargs = form
            assert issubclass(form_cls, pytis.web.BrowseForm), form_cls
            assert isinstance(form_kwargs, dict), form_kwargs
        else:
            assert form is None or issubclass(form, pytis.web.BrowseForm), form
            form_cls = form
            form_kwargs = {}
        assert enabled is None or isinstance(enabled, collections.Callable), enabled
        self._form_cls = form_cls
        self._form_kwargs = form_kwargs
        self._enabled = enabled

    def form_cls(self):
        return self._form_cls

    def form_kwargs(self):
        return self._form_kwargs

    def enabled(self):
        return self._enabled
    

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
            #if module_instance.__class__ is not cls:
            #    # Dispose the instance if the class definition has changed.
            #    raise KeyError()
        except KeyError:
            cls = self.wiking_module_cls(name)
            module_instance = cls(name, **kwargs)
            self._wiking_module_instance_cache[key] = module_instance
        return module_instance

    def available_modules(self):
        """Return a tuple of classes of all available Wiking modules."""
        return [module_cls for name, module_cls in self.walk(Module)]
    

def module(name):
    """Return the instance of given Wiking module.

    @type name: str
    @param name: Module name

    Raises: wiking.util.ResolverError if no such module is found in the current
    resolver configuration.

    This is the official way to retrieve Wiking modules within the application.
    All other means, such as the method 'Module._module()' or using
    wiking.cfg.resolver directly are now deprecated.

    """
    return wiking.cfg.resolver.wiking_module(name)

    
class DateTime(pytis.data.DateTime):
    """Pytis DateTime type which exports as a 'lcg.LocalizableDateTime'."""
    
    def __init__(self, show_time=True, exact=False, leading_zeros=True, **kwargs):
        self._exact = exact
        self._show_time = show_time
        self._leading_zeros = leading_zeros
        format = '%Y-%m-%d %H:%M'
        if exact:
            format += ':%S'
        super(DateTime, self).__init__(format=format, **kwargs)

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
    """Pytis Date type which exports as a 'lcg.LocalizableDateTime'."""

    def __init__(self, leading_zeros=True, **kwargs):
        self._leading_zeros = leading_zeros
        super(Date, self).__init__(format='%Y-%m-%d', **kwargs)

    def _export(self, value, show_weekday=False, **kwargs):
        result = super(Date, self)._export(value, **kwargs)
        return lcg.LocalizableDateTime(result, show_weekday=show_weekday,
                                       leading_zeros=self._leading_zeros)

class Time(pytis.data.Time):
    """Pytis Time type which exports as a 'lcg.LocalizableTime'."""

    def __init__(self, exact=False, **kwargs):
        self._exact = exact
        format = '%H:%M'
        if exact:
            format += ':%S'
        super(Time, self).__init__(format=format, **kwargs)
    
    def exact(self):
        return self._exact
        
    def _export(self, value, **kwargs):
        return lcg.LocalizableTime(super(Time, self)._export(value, **kwargs))


# ============================================================================
# Misc functions
# ============================================================================

def serve_file(req, path, content_type, filename=None, lock=False):
    """Return 'wiking.Response' instance to send the contents of a given file to the client.

    Arguments:
      path -- Full path to the file in server's filesystem.
      content_type -- The value to be used for the 'Content-Type' HTTP
        header (basestring).
      filename -- File name to be used for the 'Content-Disposition' HTTP header.
         This will force the browser to save the file under given file name instead
         of displaying it.
      lock -- Iff True, shared lock will be aquired on the file while it is served.

    'wiking.NotFound' exception is raised if the file does not exist.

    Important note: The file size is read in advance to determine the Content-Lenght header.
    If the file is changed before it gets sent, the result may be incorrect.
    
    """
    try:
        info = os.stat(path)
    except OSError:
        log(OPR, "File not found:", path)
        raise wiking.NotFound()
    mtime = datetime.datetime.utcfromtimestamp(info.st_mtime)
    since_header = req.header('If-Modified-Since')
    if since_header:
        try:
            since = parse_http_date(since_header)
        except:
            # Ignore the 'If-Modified-Since' header if the date format is
            # invalid.
            pass
        else:
            if mtime == since:
                return wiking.Response('', status_code=httplib.NOT_MODIFIED,
                                       content_type=content_type)
    headers = (('Last-Modified', format_http_date(mtime)),)
    def generator():
        f = file(path)
        if lock:
            import fcntl
            fcntl.lockf(f, fcntl.LOCK_SH)
        try:
            while True:
                # Read the file in 0.5MB chunks.
                data = f.read(524288)
                if not data:
                    break
                yield data
        finally:
            if lock:
                fcntl.lockf(f, fcntl.LOCK_UN)
            f.close()
    return wiking.Response(generator(), content_type=content_type, content_length=info.st_size,
                           filename=filename, headers=headers)

def timeit(func, *args, **kwargs):
    """Measure the function execution time.

    Invokes the function 'func' with given arguments and returns the triple
    (function result, processor time, wall time), both times in microseconds.

    """
    t1, t2 = time.clock(), time.time()
    result = func(*args, **kwargs)
    return result,  time.clock() - t1, time.time() - t2


class MailAttachment(object):
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
        assert file_name is None or isinstance(file_name, basestring), ('type error', file_name,)
        assert stream is None or hasattr(stream, 'read'), ('type error', stream,)
        assert isinstance(type, basestring), ('type error', type,)
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
              smtp_server=None, smtp_port=None):
    """Send a MIME e-mail message.

    Arguments:

      addr -- recipient address as a string or sequence of recipient addresses
      subject -- message subject as a string or unicode
      text -- message text as a string or unicode
      sender -- sender email address as a string; if None, the address specified by the
        configuration option `default_sender_address' is used.
      sender_name -- optional human readable sender name as a string or
        unicode; if not None, the name will be added to the 'From' header in
        the standard form: "sender name" <sender@email>.  Proper encoding is
        taken care of when necessary.
      html -- HTML part of the message as string or unicode
      export -- iff true, create the HTML part of the message by parsing 'text' as LCG Structured
        text and exporting it to HTML.
      lang -- ISO language code as a string; if not None, message 'subject', 'text' and 'html' will
         be translated into given language (if they are LCG translatable strings)
      cc -- sequence of other recipient string addresses
      headers -- additional headers to insert into the mail; it must be a tuple
        of pairs (HEADER, VALUE) where HEADER is an ASCII string containing
        the header name (without the final colon) and value is an ASCII string
        containing the header value
      attachments -- sequence of 'MailAttachment' instances describing the objects to attach
        to the mail
      smtp_server -- SMTP server name to use for sending the message as a
        string; if 'None', server given in configuration is used
      smtp_port -- SMTP port to use for sending the message as a
        number; if 'None', server given in configuration is used
      
    """
    assert isinstance(addr, (basestring, tuple, list,)), ('type error', addr,)
    assert isinstance(subject, basestring), ('type error', subject,)
    assert isinstance(text, basestring), ('type error', text,)
    assert sender is None or isinstance(sender, basestring), ('type error', sender,)
    assert sender_name is None or isinstance(sender_name, basestring), ('type error', sender_name,)
    assert html is None or isinstance(html, basestring), ('type error', html,)
    assert isinstance(export, bool), ('type error', bool,)
    assert lang is None or isinstance(lang, basestring), ('type error', lang,)
    assert isinstance(cc, (tuple, list,)), ('type error', cc,)
    assert smtp_server is None or isinstance(smtp_server, basestring), ('type error', smtp_server,)
    assert smtp_port is None or isinstance(smtp_port, int), ('type error', smtp_port,)
    if __debug__:
        for a in attachments:
            assert isinstance(a, MailAttachment), ('type error', attachments, a,)
    if isinstance(addr, (tuple, list,)):
        addr = string.join(addr, ', ')
    from email.mime.multipart import MIMEMultipart
    from email.header import Header
    if attachments:
        multipart_type = 'mixed'
    else:
        multipart_type = 'alternative'
    msg = MIMEMultipart(multipart_type)
    localizer = lcg.Localizer(lang, translation_path=wiking.cfg.translation_path)

    
    if isinstance(text, unicode):
        text = localizer.localize(text)
    if not sender or sender == '-': # Hack: '-' is the Wiking CMS Admin default value...
        sender = wiking.cfg.default_sender_address
    if sender_name:
        sender = '"%s" <%s>' % (Header(sender_name, 'utf-8').encode(), sender)
    # Set up message headers.
    msg['From'] = sender
    msg['To'] = addr
    if cc:
        msg['Cc'] = Header(string.join(cc, ', '), 'utf-8')
    translated_subject = localizer.localize(subject)
    try:
        encoded_subject = translated_subject.encode('ascii')
    except UnicodeEncodeError:
        encoded_subject = Header(translated_subject, 'utf-8')
    msg['Subject'] = encoded_subject
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
        html = "<html>\n"+ content.export(context) +"\n</html>\n"
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
    assert isinstance(address, basestring)
    import dns.resolver
    import smtplib
    try:
        # DNS query doesn't work with unicode
        address = str(address) 
        # We validate only common addresses, not pathological cases
        __, domain = address.split('@')
    except (UnicodeEncodeError, ValueError):
        return False, _("Invalid format")
    try:
        mxhosts = dns.resolver.query(domain, 'MX')
    except dns.resolver.NoAnswer:
        mxhosts = None
    except dns.resolver.NXDOMAIN:
        # Translators: Computer terminology. `gmail.com' is a domain name in email address
        # `joe@gmail.com'.
        return False, _("Domain not found")
    except Exception as e:
        return False, str(e) or e.__class__.__name__
    if mxhosts is None:
        try:
            ahosts = dns.resolver.query(domain, 'A')
        except dns.resolver.NoAnswer:
            return False, _("Domain not found")
        except Exception as e:
            return False, str(e) or e.__class__.__name__
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
                reasons += ('%s: %s; ' % (host, e,))
        else:
            return False, reasons
    return True, None


def cmp_versions(v1, v2):
    """Compare version strings, such as '0.3.1' and return the result.

    The returned value is -1, 0 or 1 such as for the builtin 'cmp()' function.
    
    """
    v1a = [int(v) for v in v1.split('.')]
    v2a = [int(v) for v in v2.split('.')]
    for (n1, n2) in zip(v1a, v2a):
        c = cmp(n1, n2)
        if c != 0:
            return c
    return 0

_ABS_URI_MATCHER = re.compile(r'^((https?|ftp)://[^/]+)(.*)$')

def make_uri(base, *args, **kwargs):
    """Deprecated: Use 'Request.make_uri()' instead."""
    if base.startswith('mailto:'):
        uri = base
    else:
        match = _ABS_URI_MATCHER.match(base)
        if match:
            uri = match.group(1) + urllib.quote(match.group(3).encode('utf-8'))
        else:
            uri = urllib.quote(base.encode('utf-8'))
    if args and isinstance(args[0], basestring):
        uri += '#'+ urllib.quote(unicode(args[0]).encode('utf-8'))
        args = args[1:]
    query = ';'.join([k +"="+ urllib.quote_plus(unicode(v).encode('utf-8'))
                      for k, v in args + tuple(kwargs.items()) if v is not None])
    if query:
        uri += '?'+ query
    return uri

_WKDAY = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun',)
_MONTH = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',)
    
def format_http_date(dt):
    """Return datetime as a basestring in the RFC 1123 format.

    Arguments:

      dt -- 'datetime.datetime' instance to be formatted

    """
    formatted = dt.strftime('%%s, %d %%s %Y %H:%M:%S GMT')
    formatted = formatted % (_WKDAY[dt.weekday()], _MONTH[dt.month-1],)
    return formatted

def parse_http_date(date_string):
    """Return datetime corresponding to RFC 2616 date_string.

    Arguments:
    
      date_string -- basestring representing date and time in one of the
        formats supported by RFC 2616

    Return corresponding 'datetime.datetime' instance in UTC.
    
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
            date_string = '%s%02d%s' % (date_string[:pos], i+1, date_string[pos+3:],)
            break
    # Parse the date
    dt = None
    for format_ in ('%d %m %Y %H:%M:%S', '%d-%m-%y %H:%M:%S', '%m %d %H:%M:%S %Y',):
        try:
            dt = datetime.datetime.strptime(date_string, format_)
            break
        except ValueError:
            pass
    if dt is None:
        raise Exception("Invalid date format")
    if tz_offset is not None:
        dt -= tz_offset
    return dt

def pdf_document(content, lang):
    """Return PDF document created from 'lcg_content'.

    Arguments:

      content -- document content, sequence of 'lcg.Content' instances
      lang -- document language as an ISO 639-1 Alpha-2 lowercase
        language code string or 'None'

    """
    assert isinstance(content, (list, tuple)), content
    assert all([isinstance(c, lcg.Content) for c in content])
    exporter = lcg.pdf.PDFExporter()
    children = []
    for i in range(len(content)):
        children.append(lcg.ContentNode(id='wiking%d' % (i,), title=' ', content=content[i]))
    lcg_content = lcg.ContentNode(id='__dummy', content=lcg.Content(), children=children)
    context = exporter.context(lcg_content, lang)
    pdf = exporter.export(context)
    return pdf

def generate_random_string(length):
    """Return a random string of given length."""
    #import base64
    try:
        code = ''.join(['%02x' % ord(c) for c in os.urandom(length/2+1)])
    except NotImplementedError:
        import random
        random.seed()
        code = ''.join(['%02x' % random.randint(0, 255) for i in range(length/2+1)])
    return code[:length]
