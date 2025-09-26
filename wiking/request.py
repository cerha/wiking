# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2016 OUI Technology Ltd.
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

import re
import string
import types
import datetime

import pytis
import pytis.web
import lcg
import wiking
from wiking import log, OPR, format_http_date, parse_http_date, Message

import http.cookies
import http.client
import urllib.parse
import urllib.error


_ = lcg.TranslatableTextFactory('wiking')


class ClosedConnection(Exception):
    """Exception raised when the client closes the connection during communication."""


class FileUpload(pytis.web.FileUpload):
    """Generic representation of uploaded file.

    The interface is defined by the 'pytis.web.FileUpload' class with no Wiking
    specific extensions.  The implementation relies on receiving a field object
    compatible with cgi.FieldStorage class.

    """

    def __init__(self, field, encoding):
        self._field = field
        self._filename = re.split(r'[\\/:]', field.filename)[-1]

    def file(self):
        return self._field.file

    def filename(self):
        return self._filename

    def mime_type(self):
        return self._field.type


class ServerInterface(pytis.web.Request):
    """Generic HTTP server interface specification.

    The interface is derived from 'pytis.web.Request' class with additional
    Wiking specific extensions.  This generic interface must be implemented by
    particular web server interface drivers.

    The goal of the interface it to provide access the HTTP request -- querying
    and manipulating incoming request headers, outgoing response headers, and
    other HTTP parameters.

    The class 'Request' then defines additional methods to be used by wiking
    applications.  The web server interface methods are defined here separately
    just for the clarity's sake.  The web server interface drivers should be
    derived from 'Request', not from this class directly.

    """

    def root(self):
        """Return the root URI of the current application.

        Returns None when the current application runs in the root of the web
        server.  If not None, it is a string value starting with a slash.  This
        is typically used to run multiple applications at one server, where
        each application has its own root.

        """
        pass

    def uri(self):
        """Return request URI path relative to application's root URI.

        The returned URI is a string value, which normally starts with a slash
        and continues with an arbitrary number of path elements separated by
        slashes.  Transfer encoding and HTTP escapes are decoded.

        """
        pass

    def unparsed_uri(self):
        """Return URI path including any request parameters (query string).

        Transfer encoding and HTTP escapes are not decoded.

        """
        pass

    def method(self):
        """Return the used HTTP request method.

        The returned value is a string.  One of 'GET', 'POST', 'PUT', 'DELETE',
        etc.

        """
        pass

    def param(self, name, default=None):
        """Return the value of request parameter 'name' or 'default' if not present.

        The returned value is a string (with HTTP escapes decoded) for ordinary
        parameters, a 'FileUpload' instance for uploaded multipart data or a
        sequence of such values when multiple values of the parameter were sent
        with the request.

        """
        pass

    def params(self):
        """Return the names of all request parameters."""
        pass

    def has_param(self, name):
        """Return true if the parameter 'name' was sent with the request."""
        return name in self.params()

    def set_param(self, name, value):
        """Set the value of given request parameter as if it was passed.

        Arguments:
          name -- parameter name as a string.
          value -- string value to set or None to remove the parameter.

        """
        pass

    def header(self, name, default=None):
        """Return value of given (incomming) request HTTP header or 'default' if unset."""
        pass

    def set_header(self, name, value):
        """Set the value of given (outgoing) response HTTP header.

        You should always pass response headers along with the
        'wiking.Response' instance instead of calling this method directly
        within the application code.

        """
        pass

    def port(self):
        """Return the current connection server port id as int."""
        pass

    def https(self):
        """Return True if the current connection is secured by HTTPS."""
        pass

    def remote_host(self):
        """Return the remote host address.

        Returns the HTTP client address, in the form of fully-qualified domain
        name if it can be resolved, or its IP address otherwise.

        """
        pass

    def server_hostname(self):
        """Return the server's fully qualified domain name as a string.

        Each virtual server may have several names (aliases) through which it
        can be accessed, such as 'www.yourdomain.com' and 'www.yourdomain.org'.
        This method returns the name used for the current request.  Use the
        configuration variable 'wiking.cfg.server_hostname' if you need the
        globally unique server name (which normally corresponds to the main
        server name).

        """
        pass

    def primary_server_hostname(self):
        """Return the fully qualified domain name of the primary server as a string.

        As oposed to 'server_hostname()', this method should return the same
        result for all requests which belong to the same (virtual) server.  If
        this information is not available from the request environment, None is
        returned.  In this case the administrator is forced to set the
        configuration variable 'server_hostname' manually.  Thus this method is
        not designed to be used in applications.  It is only used by Wiking
        internally to determine the default value of
        'wiking.cfg.server_hostname'.

        """
        pass

    def start_http_response(self, status_code):
        """Start the HTTP response.

        HTTP response headers will be sent to the client (any 'set_header()'
        calls after calling this method are ignored).  This method must be
        called before returning the request processing result.

        This is a low level server interface method.  See also
        'Request.start_response()' for a more convenient application interface
        method.

        Raise 'ClosedConnection' if the client closes the connection during the
        operation.

        """
        pass

    def option(self, name, default=None):
        pass


class Request(ServerInterface):
    """Wiking HTTP request representation.

    This class relies on the methods defined by the 'ServerInterface'
    class to access HTTP request data and additional implements methods
    specific for the Wiking request handling process on top of the server
    interface methods.  See the Wiking Developer's Documentation for an
    overview.

    """

    class ForwardInfo:
        """Request forwarding information.

        The method 'forward()' automatically adds forward information (as an
        instance of the 'ForwardInfo' class) to the stack, which may be later
        inspected through the method 'forwards()'.

        """

        def __init__(self, module, resolved_path, unresolved_path, **kwargs):
            """Arguments:

              module -- the handler instance to which the request was forwarded
              resolved_path -- sequence of request path items (strings)
                corresponding to the resolved portion of the path at the time
                of the forward
              unresolved_path -- sequence of request path items (strings)
                corresponding to the unresolved portion of the path at the time
                of the forward
              kwargs -- any keyword arguments passed to the forward method
                call.  These arguments may be later inspected through the
                'arg()' method and make it possible to pass any application
                defined data for later inspection.

            """
            self._module = module
            self._resolved_path = tuple(resolved_path)
            self._unresolved_path = tuple(unresolved_path)
            self._data = kwargs

        def module(self):
            """Return the 'module' to which this forward was passed."""
            return self._module

        def resolved_path(self):
            """Return resolved portion of the path as a tuple."""
            return self._resolved_path

        def unresolved_path(self):
            """Return unresolved portion of the path as a tuple."""
            return self._unresolved_path

        def uri(self):
            """Return the string URI corresponding to 'resolved_path'."""
            return '/' + '/'.join(self._resolved_path)

        def arg(self, name):
            """Return the value of keyword argument 'name' passed to the constructor or None."""
            try:
                return self._data[name]
            except KeyError:
                return None

    _MAXIMIZED_MODE_COOKIE = 'wiking_maximized_mode'
    _MESSAGES_COOKIE = 'wiking_messages'
    _TZ_OFFSETS_COOKIE = 'wiking_tz_offsets'
    _UNDEFINED = object()

    INFO = Message.INFO
    """Message type constant for informational messages."""
    SUCCESS = Message.SUCCESS
    """Message type constant for success messages."""
    WARNING = Message.WARNING
    """Message type constant for warning messages."""
    ERROR = Message.ERROR
    """Message type constant for error messages."""
    HEADING = 'HEADING'
    """Message type constant for messages to be put into document heading."""
    _MESSAGE_TYPES = (INFO, SUCCESS, WARNING, ERROR, HEADING,)

    _ABS_URI_MATCHER = re.compile(r'^((https?|ftp)://[^/]+)(.*)$')

    def __init__(self, encoding):
        # NOTE: The request constructor should never rely on global
        # configuration values as the first Request instance is created before
        # the wiking.Handler instance and the configuration is initialized in
        # wiking.Handler constructor.
        super(Request, self).__init__()
        self._encoding = encoding
        self._forwards = []
        self._module_uri = {}
        self._user = self._UNDEFINED
        self._cookies = http.cookies.SimpleCookie(self.header('Cookie'))
        self._preferred_language = None
        self._preferred_languages = None
        self._timezone = self._UNDEFINED
        self._localizer = {}
        self._decryption_password = self._init_decryption_password()
        self._messages = self._init_messages()
        self._is_api_request = None
        if self.has_param('maximize'):
            self._maximized = self.param('maximize') == '1'
            self.set_cookie(self._MAXIMIZED_MODE_COOKIE, self._maximized and 'yes' or 'no')
        else:
            self._maximized = self.cookie(self._MAXIMIZED_MODE_COOKIE) == 'yes'
        self.path = [item for item in self.uri().split('/')[1:] if item]
        if '..' in self.path:
            # Prevent directory traversal attacs globally (no need to handle them all around).
            raise wiking.Forbidden()
        self.unresolved_path = list(self.path)

    def _init_decryption_password(self):
        password = None
        if self.has_param('__decryption_password'):
            password = self.param('__decryption_password')
            self.set_param('__decryption_password', None)
        return password

    def _init_messages(self):
        # Attempt to unpack the messages previously stored before request
        # redirection (if this is a redirected request).
        messages = []
        stored = self.cookie(self._MESSAGES_COOKIE)
        if stored:
            lines = stored.splitlines()
            uri = urllib.parse.unquote(lines[0])
            if uri == self.server_uri(current=True) + self.unparsed_uri():
                # Storing data on client side is always problematic.  In case of
                # messages there is not much danger in it, but still it may
                # allow interesting tricks.  Storing the messages in the
                # database (server side) might be more appropriate, but would be
                # application dependent.  It might be a good idea to add this
                # possibility as optional in future.
                for line in lines[1:]:
                    try:
                        mtype, formatted, quoted = line.split(':', 2)
                        if mtype not in self._MESSAGE_TYPES or formatted not in ('t', 'f'):
                            raise ValueError("Invalid values:", mtype, formatted)
                        message = urllib.parse.unquote(quoted)
                    except Exception as e:
                        log(OPR, "Error unpacking stored messages:", e)
                    else:
                        messages.append((message, mtype, formatted == 't'))
                self.set_cookie(self._MESSAGES_COOKIE, None)
        return messages

    def _parse_accept_header(self, header):
        """Return the items present in given HTTP header.

        HTTP headers, such as 'Accept' or 'Accept-Language' share the same
        syntax for expressing multiple accepted variants and their precedence.
        For example the 'Accept' header may have the following value:

        text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8

        This method parses the header value and returns a list of items.  Each
        item has a value (string) and parameters (dictionary) which may be
        accessed via 'item.value' and 'item.params'.  The special parameter 'q'
        (if present) has a float value, other parameters have string values.

        The returned list is sorted in the order of precedence given by the
        parameter 'q' (as describerd by the HTTP standard).  The items with
        higher precedence come first.

        Any items with invalid syntax or values are ignored.

        """
        class Item:
            def __init__(self, value, params):
                self.value = value
                self.params = params

        items = []
        for item in self.header(header, '').split(','):
            try:
                if ';' in item:
                    parts = item.split(';')
                    value = parts[0].strip()
                    params = dict([[x.strip() for x in part.split('=', 1)]
                                   for part in parts[1:]])
                    if 'q' in params:
                        q = float(params['q'])
                        if q > 1.0 or q < 0.0:
                            continue
                        params['q'] = q
                else:
                    value, params = item.strip(), {}
            except ValueError:
                continue
            if value:
                items.append(Item(value, params))

        return reversed(sorted(items, key=lambda item: item.params.get('q', 1.0)))

    def cookie(self, name, default=None):
        """Get the value of given cookie as a string or return DEFAULT if the cookie was not set."""
        if name in self._cookies:
            try:
                return self._cookies[name].value
            except UnicodeDecodeError:
                return default
        else:
            return default

    def set_cookie(self, name, value, expires=None, domain=None, secure=False, samesite=False):
        """Set given value as a cookie with given name.

        Arguments:
          name -- cookie name as a string.
          value -- string value to store or None to remove the cookie.
          expires -- cookie expiration time in seconds or None for unlimited
            cookie.
          domain -- cookie domain restriction (browser will not send the cookie
            outside this domain).  If None, only the originating host is allowed.
          secure -- if True, the cookie will only be returned by the browser on
            secure connections.
          samesite -- treating third party sites (see
            https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Set-Cookie/SameSite)
            False corresponds to 'Lax' in HTTP spec and it is the default
            value.  The cookie is not sent on normal cross-site subrequests
            (third party site image or frame load), but is sent when a user is
            navigating to the origin site (i.e., when following a link).
            Passing True corresponds to 'Strict' in the spec an will only be
            sent in a first-party context and not be sent along with requests
            initiated by third party websites.  None is the most permissive
            option (corresponds to 'None' in the spec) and will be sent in all
            contexts, i.e. in responses to both first-party and cross-site
            requests.  The 'secure' argument must also be set in this case or
            the cookie will be blocked.

        """
        if value is None:
            if name in self._cookies:
                del self._cookies[name]
        else:
            self._cookies[name] = value
        cookie = http.cookies.SimpleCookie()
        cookie[name] = value or ''
        cookie[name]['path'] = '/'
        if expires is not None:
            cookie[name]['Expires'] = expires
        if domain is not None:
            cookie[name]['Domain'] = domain
        if secure:
            cookie[name]['Secure'] = True
        cookie[name]['SameSite'] = {
            True: 'Strict',
            False: 'Lax',
            None: 'None',
        }[samesite]
        self.set_header('Set-Cookie', cookie[name].OutputString())

    def encoding(self):
        """Return the character encoding used in HTTP communication."""
        return self._encoding

    def server_uri(self, force_https=False, current=False):
        """Return full server URI as a string.

        Arguments:
          force_https -- If True, the uri will point to an HTTPS address even
            if the current request is not on HTTPS.  This may be useful for
            redirection of links or form submissions to a secure channel.
          current -- controls which server domain name to use.  True means to
            use the result of 'server_hostname()' (see its docstring for more
            information) and False means to use the global name from
            'wiking.cfg.server_hostname'.

        The URI in the form 'http://www.yourdomain.com' is constructed
        including port and scheme specification.  If current request port
        corresponds to one of 'https_ports' configuration option (443 by
        default), the scheme is set to 'https'.  The port is also included in
        the uri if it is not the current scheme's default port (80 or 443).

        """
        if force_https:
            port = wiking.cfg.https_ports[0]
        else:
            port = self.port()
        if port in wiking.cfg.https_ports:
            scheme = 'https'
            default_port = 443
        else:
            scheme = 'http'
            default_port = 80
        if current:
            server_hostname = self.server_hostname()
        else:
            server_hostname = wiking.cfg.server_hostname
        result = scheme + '://' + server_hostname
        if port != default_port:
            result += ':' + str(port)
        return result

    def cached_since(self, mtime):
        """Return true if client's cached resource is from given 'mtime' or later.

        Arguments:
          mtime -- last modification time of the resource on the
            server as a datetime instance.  It may be a timezone
            aware instance or a naive instance in UTC.

        Returns true if the client's cached version of the requested resource
        was last modified by the given datetime or later.  It does so by
        comparing the timestamp passed by the client in the 'If-Modified-Since'
        HTTP header to given 'mtime'.  If the header was not passed or has
        invalid format, False is returned.

        In other words, true is returned if the client's cached version is
        recent enough and doesn't need to be refreshed.  The server's response
        in this case should be 304 Not Modified.

        Typical usage:

          if req.cached_since(mtime):
              raise wiking.NotModified()

        """
        header = self.header('If-Modified-Since')
        if header:
            cached_mtime = parse_http_date(header)
            if cached_mtime is not None:
                tz = mtime.tzinfo
                if tz:
                    # Convert a timezone aware datetime instance to a naive one in
                    # UTC, as parse_http_date also returns naive datetime in UTC.
                    mtime = mtime.replace(tzinfo=None) - tz.utcoffset(mtime)
                if mtime.microsecond != 0:
                    # Timestamps in HTTP are truncated to seconds by
                    # format_http_date(), so truncate the compared
                    # timstamp too to get the comparison right.
                    mtime = mtime.replace(microsecond=0)
                if cached_mtime >= mtime:
                    return True
        return False

    def start_response(self, status_code=http.client.OK, content_type=None, content_length=None,
                       last_modified=None):
        """Set some common HTTP response attributes and send the HTTP headers.

        Arguments:
          status_code -- integer number denoting the HTTP response status code
            (default is 'httplib.OK').  See the notes below concerning HTTP
            authentication.  This argument may be used as positional (it is
            guaranteed to be the first argument in future versions), altough it
            is still optional.  It is recommended to use 'httplib' constants
            for the status codes.

          content_type -- equivalent to setting 'Content-Type' by calling
            'set_header()' prior to this call.

          content_length -- equivalent to setting 'Content-Length' by calling
             'set_header()' prior to this call.

          last_modified -- last modification time as a python datetime
            instance.  Equivalent to setting 'Last-Modified' by calling
            'set_header()' prior to this call.

        This is actually just a little more convenient way of calling
        'start_http_response()' defined by the low level server API.  Calling
        this method will cause all HTTP headers to be sent to the client.  Any
        'set_header()' calls after calling this method are ignored.

        If 'status_code' is set to 401 (UNAUTHORIZED), the 'WWW-Authenticate'
        header is automatically set to 'Basic realm="<wiking.cfg.site_title>"'.
        Use the lower level method 'start_http_response()' if you want to avoid
        this side effect.

        Raises 'ClosedConnection' if the client closes the connection during
        the operation.

        The method should not be used directly by Wiking applications.
        Application code should return 'wiking.Response' and 'wiking.Handler'
        is responsible for handling it further.

        """
        if content_type is not None:
            self.set_header('Content-Type', content_type)
        if content_length is not None:
            self.set_header('Content-Length', str(content_length))
        if last_modified is not None:
            self.set_header('Last-Modified', format_http_date(last_modified))
        self.start_http_response(status_code)

    def send_response(self, data, content_type="text/html", content_length=None,
                      status_code=http.client.OK, last_modified=None):
        """Start the HTTP response and send response data to the client.

        Arguments:

          data -- respnse data as str or bytes.  String will be automatically
            encoded to bytes using the current encoding.
          content_type -- same as in 'start_response()', but the current
            encoding will be automatically appended for types "text/html",
            "application/xml", "text/css" and "text/plain".  So for example
            "text/plain" will be converted to "text/plain; charset=UTF-8".
          status_code -- same as in 'start_response()'.
          last_modified -- same as in 'start_response()'.

        This method is actually just a shorthand for calling 'start_response()'
        and returning response data in one step with additional charset
        handling.  The 'Content-Length' HTTP header is automatically set
        according to the length of 'data'.

        The method should not be used directly by Wiking applications.
        Application code should return 'wiking.Response' and 'wiking.Handler'
        is responsible for handling it further.

        """
        if isinstance(data, (list, types.GeneratorType)):
            result = data
        else:
            if isinstance(data, str):
                data = data.encode(self._encoding)
                if content_type in ("text/html", "application/xml", "text/css", "text/plain"):
                    content_type += "; charset=%s" % self._encoding
            elif not isinstance(data, bytes):
                raise Exception('Invalid data arguemnt to Request.send_response(): %s' % type(data))
            result = [data]
            if content_length is None:
                content_length = len(data)
        self.start_response(status_code, content_type=content_type, content_length=content_length,
                            last_modified=last_modified)
        return result

    def redirect(self, uri, args=(), status_code=http.client.FOUND):
        """Send an HTTP redirection response to the browser.

        Arguments:
          uri -- redirection target URI as a string.  May be relative to the
            current request server address or absolute if it begins with
            'http://' or 'https://'.  Relative URI is automatically prepended
            by current server URI, since HTTP specification requires absolute
            URIs.  The uri may not include any query arguments encoded within
            it.  If needed, the arguments must be passed separately using the
            'args' argument.
          args -- URI arguments to be encoded to the final redirection URI.
            The value may by a tuple of (NAME, VALUE) pairs or a dictionary.
            All conditions defined by 'make_uri()' apply for uri argument
            encoding.
          status_code -- HTTP status code of the response.

        This method should not be called from application code.  Raise the
        'wiking.Redirect' exception instead.

        """
        if uri.startswith('http://') or uri.startswith('https://'):
            uri = self.make_uri(uri, *args)
        else:
            if not uri.startswith('/'):
                uri = '/' + uri
            uri = self.server_uri(current=True) + self.make_uri(uri, *args)
        self.store_messages(uri)
        html = ("<html><head><title>Redirected</title></head>"
                "<body>Your request has been redirected to "
                "<a href='" + uri + "'>" + uri + "</a>.</body></html>").encode(self._encoding)
        self.set_header('Location', uri)
        return self.send_response(html, status_code=status_code, content_type="text/html")

    def store_messages(self, uri):
        """Store the current messages for the next request.

        Arguments:
          uri -- next uri for which the messages will be used.

        The messages are stored in browser's cookie to allow loading them
        within the next request.  This is typically practical for
        POST/redirect/GET where the messages are genereted while handling the
        POST request but should be displayed in the resulting GET request.
        Wiking will take care of storing the messages automatically when
        redirection is done throug Wiking's standard API (raise
        wiking.Redirect()).  You may need to call this method manually only if
        you need the same effect without redirection.  For example when the
        POST response is processed by JavaScript and the redirection is invoked
        there.

        Of course, this only works if the next request is handled by the same
        Wiking app.

        """
        if self._messages:
            # Translate the messages before quoting, since the resulting strings
            # will not be translatable anymore.  We make the assumption, that the
            # redirected request's locale will be the same as for this request,
            # but that seems quite appropriate assumption.
            lines = [urllib.parse.quote(uri.encode(self._encoding))] + \
                [':'.join((mtype, 't' if formatted else 'f',
                           urllib.parse.quote(self.localize(message).encode(self._encoding))))
                 for message, mtype, formatted in self._messages]
            self.set_cookie(self._MESSAGES_COOKIE, "\n".join(lines))

    def make_uri(self, uri, *args, **kwargs):
        """Return a URI constructed from given base URI and arguments.

        Arguments:

          uri -- base URI.  May be a relative path, such as '/xx/yy',
            absolute URI, such as 'http://host.domain.com/xx/yy' or a mailto
            URI, such as 'mailto:name@domain.com'.
          *args -- pairs (NAME, VALUE) representing arguments appended to
            'uri' in the order in which they appear.  The first positional
            argument may also be a string representing an anchor name.  If
            that's the case, the anchor is appended to 'uri' after a '#'
            sign and the first argument is not considered to be a (NAME, VALUE)
            pair.
          **kwargs -- keyword arguments representing additional arguments to
            append to the URI.  Use 'kwargs' if you don't care about the order
            of arguments in the returned URI, otherwise use 'args'.

        If any of 'args' or 'kwargs' VALUE is None, the argument is omitted.

        The URI and the arguments may be strings.  All strings are properly
        encoded in the returned URI.

        """
        quote = urllib.parse.quote
        if uri.startswith('mailto:'):
            # Many e-mail clients wouldn't replace '+' in the subject by spaces.
            quote_param = quote
        else:
            match = self._ABS_URI_MATCHER.match(uri)
            if match:
                uri = match.group(1) + quote(match.group(3))
            else:
                root = self.root()
                if root and not uri.startswith(root + '/'):
                    uri = root + uri
                uri = quote(uri)
            quote_param = urllib.parse.quote_plus
        if args and isinstance(args[0], str):
            anchor = quote(args[0])
            args = args[1:]
        else:
            anchor = None
        params = [(k, v) for k, v in args + tuple(kwargs.items()) if v is not None]
        if params:
            uri += '?' + urllib.parse.urlencode(params, quote_via=quote_param)
        if anchor:
            uri += '#' + anchor
        return uri

    def forward(self, handler, **kwargs):
        """Pass handling on to another handler keeping track of forwarding history.

        Arguments:
          handler -- 'wiking.RequestHandler' instance to handle request.
          kwargs -- all keyword arguments are passed to the 'ForwardInfo'
            instance created for this forward (later available in forward
            history using the method 'forwards()').

        Returns the result of calling 'handler.handle(req)'.

        """
        unresolved_path = self.unresolved_path
        if unresolved_path:
            resolved_path = self.path[:-len(unresolved_path)]
        else:
            resolved_path = self.path
        self._forwards.append(self.ForwardInfo(handler, resolved_path, unresolved_path, **kwargs))
        try:
            return handler.handle(self)
        finally:
            self._forwards.pop()

    def forwards(self):
        """Return tuple of `ForwardInfo' instances from current forwarding stack.

        The items are returned in the order in which the corresponding
        'forward()' calls were made.  The current 'Application', which normally
        starts the request handling, is not included in this list.

        """
        return tuple(self._forwards)

    def maximized(self):
        """Return True if Wiking maximized content mode is currently on.

        The Request instance tracks the state of maximization and
        uses cookies to make this setting persistent.

        """
        return self._maximized

    def accepted_languages(self):
        """Return tuple of language codes accepted by client sorted by preference.

        This is just a convenience method to parse the HTTP 'Accept-Language'
        header.  See the method 'preferred_languages()' for application
        specific list of preferred languages.

        """
        languages = []
        for item in self._parse_accept_header('Accept-Language'):
            lang = item.value
            if '-' in lang:
                # For now we ignore the country part and recognize just the core languages.
                lang = lang.split('-')[0].lower()
            if lang not in languages:
                languages.append(lang)
        return languages

    def preferred_languages(self):
        """Return a list of user's preferred languages in the order of their preference.

        Returns the result of curren't application's method
        'Application.preferred_languages()' and caches its result for the
        current request.

        """
        result = self._preferred_languages
        if result is None:
            application = wiking.module.Application
            self._preferred_languages = result = application.preferred_languages(self)
        return result

    def preferred_language(self, variants=None, raise_error=True):
        """Return the preferred variant from the list of available variants.

        The preference is determined by the order of acceptable languages
        returned by 'preferred_languages()'.

        Arguments:

          variants -- list of language codes of avialable language variants.
            If None (default), all languages defined by the current Wiking
            application will be considered.
          raise_error -- if false, None is returned if there is no acceptable
            variant in the list.  Otherwise NotAcceptable error is raised.

        """
        if variants is None:
            if self._preferred_language is not None:
                return self._preferred_language
            variants = wiking.module.Application.languages()
            save_default = True
        else:
            save_default = False
        for lang in self.preferred_languages():
            if lang in variants:
                if save_default:
                    self._preferred_language = lang
                return lang
        if raise_error:
            raise wiking.NotAcceptable(variants=variants)
        else:
            return None

    prefered_languages = preferred_languages
    """Misspelled method name kept for backwards compatibility. Use 'preferred_languages()'."""
    prefered_language = preferred_language
    """Misspelled method name kept for backwards compatibility. Use 'preferred_language()'."""

    def timezone(self):
        timezone = self._timezone
        if timezone is self._UNDEFINED:
            offsets = self.cookie(self._TZ_OFFSETS_COOKIE)
            try:
                summer_offset, winter_offset = [int(x) for x in
                                                urllib.parse.unquote(offsets).split(';')]
            except (ValueError, TypeError, AttributeError):
                timezone = wiking.cfg.default_timezone
            else:
                timezone = wiking.TZInfo(summer_offset, winter_offset)
            self._timezone = timezone
        return timezone

    def localize(self, string, lang=None):
        """Return the 'string' localized into the user's preferred language.

        Arguments:

          string -- string to localize if possible.
          lang -- target language code as a string or None.  If None, the
            current preferred language is used instead.

        Strings which are not 'lcg.Localizable' are returned without change.
        Localizable instances are returned as strings localized according to
        the current locale settings (preferred language, timezone, ...).

        This is actually just a convenience wrapper for a frequently used call
        to 'Request.localizer().localize()'.

        """
        return self.localizer(lang=lang).localize(string)

    translate = localize
    """Backwards compatibility alias - use 'localize()' instead."""

    def localizer(self, lang=None, timezone=None):
        """Return an 'lcg.Localizer()' instance for given language.

        If 'lang' is None, the current preferred language is used instead.

        Using this method is encouraged as the created instance is cached for
        the duration of the request.

        """
        if lang is None:
            lang = self.preferred_language(raise_error=False)
        try:
            localizer = self._localizer[lang]
        except KeyError:
            localizer = lcg.Localizer(lang, translation_path=wiking.cfg.translation_path,
                                      timezone=self.timezone())
            self._localizer[lang] = localizer
        return localizer

    def decryption_password(self):
        """Return decryption password as given by the user."""
        return self._decryption_password

    def user(self, require=False):
        """Return 'wiking.User' instance for the currently logged-in user.

        Arguments:

          require -- boolean flag indicating that the user is required to be
            logged (anonymous access not allowed).  If set to true and no user
            is logged, 'AuthenticationError' is raised instead of returning
            None.  If 'require' is false and no user is logged, None is
            silently returned.

        Authentication is performed on first call and the result is cached for
        the life time of the request instance.

        A 'wiking.User' instance is returned if authentication was successful
        or None if not (user is not logged or session expired).

        The authentication process makes use of the configured authentication
        providers in the order defined by the configuration option
        'authentication_providers'.  The first successful provider wins.

        'AuthenticationError' may be raised if login credentials were passed
        but are not valid (what that means depends on particular authentication
        providers).

        """
        if self._user is self._UNDEFINED:
            user = None
            try:
                for provider in wiking.cfg.authentication_providers:
                    user = provider.authenticate(self)
                    if user is not None:
                        break
            finally:
                # Make sure to set self._user even in case that authentication raises an exception.
                self._user = user
        else:
            user = self._user
        if require and user is None:
            raise wiking.AuthenticationError()
        return user

    def check_roles(self, *args):
        """Return true, iff the current user belongs to at least one of given roles.

        Arguments may be roles or nested sequences of roles, which will be
        unpacked.  Roles are represented by 'Role' instances.

        Authentication will be performed only if needed.  In other words, if
        'args' contain ANYONE, True will be returned without an attempt to
        authenticate the user.

        """
        return self.check_user_roles(self.user(), *args)

    @classmethod
    def check_user_roles(class_, user, *args):
        """Return true, iff the given user belongs to at least one of given roles.

        Arguments may be roles or nested sequences of roles, which will be
        unpacked.  Roles are represented by 'Role' instances.  'user' is a
        'User' instance or 'None'.

        Authentication will be performed only if needed.  In other words, if
        'args' contain ANYONE, True will be returned without an attempt to
        authenticate the user.

        """

        roles = []
        for arg in args:
            if isinstance(arg, (list, tuple)):
                roles.extend(arg)
            else:
                roles.append(arg)
        if Roles.ANYONE in roles:
            return True
        if user is None:
            try:
                user_roles = class_._anonymous_roles
            except AttributeError:
                # Determine the roles just once per request (may be used many times).
                application = wiking.module.Application
                user_roles = class_._anonymous_roles = application.contained_roles(Roles.ANYONE)
        else:
            user_roles = user.roles()
        for role in roles:
            if role in user_roles:
                return True
        return False

    def module_uri(self, modname):
        """Return the base URI of given Wiking module (relative to server root).

        The argument 'modname' is the Wiking module name as a string.

        If the module has no definite global path within the application, None
        may be returned.

        The URI is actually obtained from 'Application.module_uri()', but is
        cached at this level for performance reasons.  The Application may
        often need to access the database to determine the answer, so using
        this method instead of 'Application.module_uri()' is highly recommended
        unless you have a special reason not to do so.

        Implementation note: Caching is done at the level of the request
        instance, since global caching would not allow invalidation of cached
        items after mapping changes in the multiprocess server invironment.
        This method can be implemented using a global cache if this limitation
        doesn't apply in another environment.

        """
        try:
            uri = self._module_uri[modname]
        except KeyError:
            application = wiking.module.Application
            uri = self._module_uri[modname] = application.module_uri(self, modname)
        return uri

    def message(self, message, type=None, formatted=False):
        """Add a message to the stack.

        Arguments:
          message -- message text as a string.
          type -- message text as one of INFO, WARNING, ERROR, HEADING
            constants of the class.  If None, the default is INFO.  Should be
            passed as positional if not omitted.
          formatted -- If True, the message may include LCG inline markup for
            'lcg.Parser.parse_inline_markup()'.  False (the default) indicates
            a plain text message with no further processing (displayed as is).

        The stacked messages can be later retrieved using the 'messages()' method.

        """
        assert type is None or type in self._MESSAGE_TYPES
        self._messages.append((message, type or self.INFO, formatted))

    def messages(self, heading=False):
        """Return the current stack of messages as a tuple of tripples (MESSAGE, TYPE, FORMATTED).

        Arguments:

          heading -- if 'None', return all messages; if 'False', return all
            messages except for heading messages; if 'True', return only
            heading messages

        """
        if heading is None:
            messages = self._messages
        elif heading:
            messages = [m for m in self._messages if m[1] == self.HEADING]
        else:
            messages = [m for m in self._messages if m[1] != self.HEADING]
        return tuple(messages)

    def is_api_request(self):
        """Return True if the current request looks like an API request.

        API requests are such requests which require a machine readable
        respopnse, such as JSON data.  Their handling may differ from "browser"
        requests, which typically expect a human readable response, such as an
        HTML page.

        True is currently returned when 'application/json' or
        'application/vnd.*+json' appears in the HTTP header 'Accept' with a
        higher precedence than 'text/html'.

        """
        if self._is_api_request is None:
            def is_api_request():
                for item in self._parse_accept_header('Accept'):
                    mime_type = item.value
                    if mime_type == 'text/html':
                        return False
                    elif mime_type == 'application/json':
                        return True
                    elif mime_type.startswith('application/vnd.') and mime_type.endswith('+json'):
                        return True
                return False
            self._is_api_request = is_api_request()
        return self._is_api_request


class User:
    """Representation of the logged in user.

    The authentication module returns an instance of this class on successful
    authentication.  The interface defined by this class is used within the
    framework, but applications are allowed (and encouraged) to derive a class
    with an extended interface used by the application.

    The simplest way of using application-specific extensions is passing an
    arbitrary object as the 'data' constructor argument.  This doesn't require
    deriving a specific 'User' subclass, but may be a little cumbersome in some
    situations.

    """
    MALE = 'm'
    FEMALE = 'f'

    def __init__(self, login, uid=None, name=None, roles=(), email=None,
                 password=None, password_expiration=None, gender=None, lang='en',
                 uri=None, data=None):
        """Initialize the instance.

        Arguments:

          login -- user's login name as a string
          uid -- numeric user identifier (int)
          name -- visible name as a string (login is used if None)
          roles -- sequence of user roles as 'Role' instances.  Since every
            user must be authenticated, roles must always contain at least the
            role 'Roles.AUTHENTICATED'.
          email -- e-mail address as a string
          password -- user's expected authentication password or None if
            password authentication is not allowed.  The login password will be
            checked against this value for authentication to succeed.
          password_expiration -- password expiration date as a Python 'date'
            instance or None.  It is up to the application to decide whether a
            user whose password has already expired has access to the
            application.  This should be reflected in the 'roles' the user
            receives.  Regardless of the roles, however, wiking.Handler will
            automatically redirect to 'Application.password_change_uri()' if it
            is defined and if the password expired today or earlier.
          gender -- User's gender as one of MALE/FEMALE class constants or None
            if unknown
          lang -- code of the user's preferred language
          uri -- user's profile URI or None
          data -- application specific data

        Please note, that password expiration date has currently no impact on
        the authentication process.  It will just be displayed in the login
        panel, if defined.

        """
        assert isinstance(login, str), login
        assert name is None or isinstance(name, str), name
        assert isinstance(roles, (tuple, list)), roles
        assert Roles.AUTHENTICATED in roles
        self._login = login
        self._uid = uid or login
        self._name = name or login
        self._roles = tuple(roles)
        self._email = email
        self._password = password
        self._password_expiration = password_expiration
        self._uri = uri
        self._data = data
        self._lang = lang
        self._gender = gender

    def login(self):
        """Return user's login name as a string."""
        return self._login

    def uid(self):
        """Return user's identifier for ownership determination."""
        return self._uid

    def name(self):
        """Return user's visible name as a string."""
        return self._name

    def roles(self):
        """Return valid user's roles as a tuple of 'Role' instances."""
        return self._roles

    def email(self):
        """Return user's e-mail address as a string or None if not defined."""
        return self._email

    def password(self):
        """Return user's authentication password as a string or None."""
        return self._password

    def password_expiration(self):
        """Return password expiration date as a Python 'date' instance or None."""
        return self._password_expiration

    def gender(self):
        """Return the user's gender as MALE/FEMALE class constant or None if unknown."""
        return self._gender

    def lang(self):
        """Return code of the user's preferred language."""
        return self._lang

    def uri(self):
        """Return the URI of user's profile."""
        return self._uri

    def data(self):
        """Return application specific data passed to the constructor."""
        return self._data


class Role:
    """Representation of a user role.

    Every user can have assigned any number of roles.  The roles can serve
    various purposes, for instance:

     - Determining user access rights.
     - Changing presentation of forms based on the user roles.
     - Defining groups of users for any reason, e.g. for sending notifications.

    There are no strict rules on usage of user roles in an application.  The
    application can check assignments of roles to the user using
    L{Request.check_roles} method.  Refer to documentation of particular
    modules using roles for interpretation of user roles in them.  See
    L{wiking.cms.Application.authorize} for standard handling of role based
    access rights in Wiking CMS applications.

    Each role is defined by its unique identifier, returned by L{id} method.
    It identifies the role in application and databases.  Additionally there is
    a human readable name of the role for presentation in user interfaces.

    We distinguish the following basic kinds of roles:

     - Predefined special roles.  These roles are determined automatically for
       each user by the application (typically its authorization process).  It
       is not possible to assign users to these roles explicitly.  They are
       typically omitted from role listings in codebooks, with the exception of
       access rights assignments.

     - Predefined application roles.  These roles are defined by the
       application for various purposes.  These roles may be stored in the
       database and an application administrator can assign them to users in
       Wiking CMS.

     - User defined roles.  These are roles defined by an application
       administrator in Wiking CMS.  These roles are not used by the
       application directly.  They are typically used to create roles grouping
       several application roles into a single application role, see
       L{wiking.cms.RoleSets} for more information.  User defined roles are not
       defined in the application code, they are stored in the database.

    Predefined application roles are defined by L{Roles} class.

    """

    def __init__(self, role_id, name):
        """
        @type role_id: string
        @param role_id: Unique identifier of the role.  It may contain only
          English letters, digits, underscores and dots.  Dots are reserved for
          separating identifier components, e.g. to add prefixes to user
          defined roles to avoid name conflicts with standard application roles.
        @type name: str
        @param name: Human readable name of the role.
        """
        self._id = role_id
        self._name = name

    def __repr__(self):
        return "<role '%s'>" % self._id

    def __eq__(self, other):
        """Two roles are equal if their unique identifiers are equal."""
        if isinstance(other, Role):
            return self._id == other._id
        else:
            return NotImplemented

    def id(self):
        """
        @rtype: string
        @return: Unique identifier of the role.
        """
        return self._id

    def name(self):
        """
        @rtype: str
        @return: Human readable name of the role.
        """
        return self._name


class Roles:
    """Set of available user roles.

    This particular class defines a very limited set of special purpose Wiking
    roles.  Wiking applications may use the roles defined here, subclass this
    class to define additional predefined roles or use application specific and
    user defined roles.  Roles are represented by L{Role} instances.
    Subclasses which define additional roles must override the methods
    L{__getitem__} and L{all_roles()} to return the appropriate results.

    Predefined roles are defined as public constants of the class.

    You can get complete set of roles defined by an application by calling
    L{all_roles} method.

    @see: L{Role} for information about various kinds of roles.

    """
    # Translators: Short description of a user group purpose.
    ANYONE = Role('anyone', _("Anyone"))
    """Anyone, even a user who is not logged-in."""
    # Translators: Short description of a user group purpose.
    AUTHENTICATED = Role('authenticated', _("Any authenticated user"))
    """Any authenticated user.

    Note that authenticated users may be further split into more specific
    groups of authenticated users, based on their actual level of access to the
    application.  See L{wiking.cms.Roles} for examples of such more specific
    roles.

    """

    @classmethod
    def _predefined_roles(self):
        """
        @rtype: tuple of L{Role}s
        @return: All roles statically predefined as public constants of this class.
        """
        roles = []
        for name in dir(self):
            if name[0] in string.ascii_uppercase:
                value = getattr(self, name)
                if isinstance(value, Role):
                    roles.append(value)
        return tuple(roles)

    def __getitem__(self, role_id):
        """
        @type role_id: string
        @param role_id: Unique identifier of the role to be returned.

        @rtype: L{Role}
        @return: The role identified by C{role_id}.

        @raise KeyError: There is no role with C{role_id} as its unique
          identifier.
        """
        for role in self._predefined_roles():
            if role.id() == role_id:
                return role
        raise KeyError(role_id)

    def all_roles(self):
        """
        @rtype: sequence of L{Role}s
        @return: All the roles available in the application.
        """
        return self._predefined_roles()
