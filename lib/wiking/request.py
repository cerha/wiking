# Copyright (C) 2006-2009 Brailcom, o.p.s.
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

try:
    # We need to be able to import the module if mod_python is not loaded.
    from mod_python import apache
    import mod_python.util
except:
    pass
else:
    # Modify pytis configuration only in the apache environment.
    import config
    config.dblisten = False
    config.log_exclude = [pytis.util.ACTION, pytis.util.EVENT, pytis.util.DEBUG]
    del config
    
import Cookie

_ = lcg.TranslatableTextFactory('wiking')

DAY = 86400

class FileUpload(pytis.web.FileUpload):
    """Mod_python specific implementation of pytis FileUpload interface."""
    def __init__(self, field, encoding):
        self._field = field
        self._filename = re.split(r'[\\/:]', unicode(field.filename, encoding))[-1]
    def file(self):
        return self._field.file
    def filename(self):
        return self._filename
    def type(self):
        return self._field.type


class ClosedConnection(Exception):
    """Exception raised when the client closes the connection during communication."""
    
class Request(pytis.web.Request):
    """Mod_python request wrapper implementing the pytis request interface."""
    
    _UNIX_NEWLINE = re.compile("(?<!\r)\n")
    
    def __init__(self, req, encoding='utf-8'):
        self._req = req
        self._encoding = encoding
        self._cookies = Cookie.SimpleCookie(self.header('Cookie'))
        # Store params and options in real dictionaries (not mod_python's mp_table).
        self._options = self._init_options() 
        self._params = self._init_params()
        self._uri = uri = unicode(req.uri, encoding)
        self.path = self._init_path(uri)

    def _init_options(self):
        options = self._req.get_options()
        return dict([(o, options[o]) for o in options.keys()])
        
    def _init_params(self):
        def init_value(value):
            if isinstance(value, (tuple, list)):
                return tuple([init_value(v) for v in value])
            elif isinstance(value, mod_python.util.Field):
                return FileUpload(value, self._encoding)
            else:
                return unicode(value, self._encoding)
        fields = mod_python.util.FieldStorage(self._req)
        return dict([(k, init_value(fields[k])) for k in fields.keys()])

    def _init_path(self, uri):
        return [item for item in uri.split('/')[1:] if item]

    def _cookie_path(self):
        return '/'

    # Methods implementing the pytis Request interface:
    
    def has_param(self, name):
        return self._params.has_key(name)
        
    def param(self, name, default=None):
        return self._params.get(name, default)
        
    def cookie(self, name, default=None):
        """Get the value of given cookie as unicode or return DEFAULT if cookie was not set."""
        if self._cookies.has_key(name):
            try:
                return unicode(self._cookies[name].value, self._encoding)
            except UnicodeDecodeError:
                return default
        else:
            return default
        
    def set_cookie(self, name, value, expires=None, secure=False):
        """Set given value as a cookie with given name.

        Arguments:
          name -- cookie name as a string.
          value -- unicode value to store or None to remove the cookie.
          expires -- cookie expiration time in seconds or None for unlimited cookie.
          secure -- if True, the cookie will only be returned by the browser on secure connections.

        """
        if value is None:
            if self._cookies.has_key(name):
                del self._cookies[name]
        else:
            if isinstance(value, unicode):
                value = value.encode(self._encoding)
            self._cookies[name] = value
        c = Cookie.SimpleCookie()
        c[name] = value or ''
        #c[name]['domain'] = self._req.connection.local_host
        c[name]['path'] = self._cookie_path()
        if expires is not None:
            c[name]['expires'] = expires
        if secure:
            c[name]['secure'] = True
        cookie = c[name].OutputString()
        self._req.headers_out.add("Set-Cookie", cookie)

    # Additional methods:

    def uri(self):
        return self._uri
        
    def set_param(self, name, value):
        self._params[name] = value
        
    def params(self):
        return self._params.keys()
    
    def option(self, name, default=None):
        return self._options.get(name, default)

    def header(self, name, default=None):
        try:
            return self._req.headers_in[name]
        except KeyError:
            return default

    def set_header(self, name, value):
        self._req.headers_out.add(name, value)
        
    def https(self):
        """Return true if https is on."""
        return self._req.connection.local_addr[1] == cfg.https_port
    
    def remote_host(self):
        return self._req.get_remote_host()

    def server_hostname(self, current=False):
        """Return the server's fully qualified domain name as a string.

        Each virtual server may have several names through which it can be accessed, such as
        'www.yourdomain.com' and 'www.yourdomain.org'.  One of them is the main one (i.e. as
        defined in web server configuration).  The main name is returned by default, but if
        'current' is True, the name used in the current request URI is returned.

        """
        if current:
            return self._req.hostname
        else:
            return self._req.server.server_hostname

    def server_uri(self, force_https=False, current=False):
        """Return full server URI as a string.

        Arguments:
          force_https -- If True, the uri will point to an HTTPS address even if the current
            request is not on HTTPS.  This may be useful for redirection of links or form
            submissions to a secure channel.
          current -- controls which server domain name to use.  Corrensponds to the same argument
            of 'server_hostname()'.
        
        The URI in the form 'http://www.yourdomain.com' is constructed including port and protocol
        specification.  If current request port corresponds to 'https_port' configuration option
        (443 by default), the protocol is set to 'https'.  The port is also included in the uri if
        it is not the current protocol's default port (80 or 443).

        """
        if force_https:
            port = cfg.https_port
        else:
            port = self._req.connection.local_addr[1]
        if port == cfg.https_port:
            protocol = 'https'
            default_port = 443
        else:
            protocol = 'http'
            default_port = 80
        result = protocol + '://'+ self.server_hostname(current=current)
        if port != default_port:
            result += ':'+ str(port)
        return result

    def certificate(self):
        """Return verified client TLS/SSL certificate.

        If no client certificate was provided or it wasn't verified by the web
        server, return 'None'."""
        if self._req.ssl_var_lookup('SSL_CLIENT_VERIFY') == 'SUCCESS':
            certificate = self._req.ssl_var_lookup('SSL_CLIENT_CERT')
        else:
            certificate = None
        return certificate

    def set_status(self, status):
        self._req.status = status

    def send_http_header(self, content_type, lenght=None):
        self._req.content_type = content_type
        if lenght is not None:
            self._req.set_content_length(lenght)
        try:
            self._req.send_http_header()
        except IOError, e:
            raise ClosedConnection(str(e))

    def write(self, data):
        try:
            self._req.write(data)
        except IOError, e:
            raise ClosedConnection(str(e))
        
    def done(self):
        return apache.OK
    
    def result(self, data, content_type="text/html"):
        if content_type in ("text/html", "application/xml", "text/css", "text/plain") \
               and isinstance(data, unicode):
            content_type += "; charset=%s" % self._encoding
            #data = self._UNIX_NEWLINE.sub("\r\n", data)
            data = data.encode(self._encoding)
        self.send_http_header(content_type, len(data))
        self.write(data)
        return apache.OK

    def serve_file(self, filename, content_type, lock=False):
        """Send the contents of given file to the remote host.

        Arguments:
          filename -- full path to the file
          content_type -- Content-Type header as a string
          lock -- iff True, shared lock will be aquired on the file while it is served.

        'NotFound' exception is raised if the file does not exist.

        Important note: The file size is read in advance to determine the Content-Lenght header.
        If the file is changed before it gets sent, the result may be incorrect.
        
        """
        try:
            size = os.stat(filename).st_size
        except OSError:
            raise NotFound
        self.send_http_header(content_type, size)
        f = file(filename)
        if lock:
            import fcntl
            fcntl.lockf(f, fcntl.LOCK_SH)
        try:
            while True:
                # Read the file in 0.5MB chunks.
                data = f.read(524288)
                if not data:
                    break
                self.write(data)
        finally:
            if lock:
                fcntl.lockf(f, fcntl.LOCK_UN)
            f.close()
        return apache.OK        

    def redirect(self, uri, permanent=False):
        self._req.content_type = "text/html"
        try:
            self._req.send_http_header()
        except IOError, e:
            raise ClosedConnection(str(e))
        self._req.status = permanent and apache.HTTP_MOVED_PERMANENTLY or \
                           apache.HTTP_MOVED_TEMPORARILY
        self.set_header('Location', uri)
        self.write("<html><head><title>Redirected</title></head>"
                   "<body>Your request has been redirected to "
                   "<a href='"+uri+"'>"+uri+"</a>.</body></html>")
        return apache.OK


class WikingRequest(Request):
    """Wiking application specific request object.

    This class adds some features which are quite specific for the Wiking request handling
    process.  See the Wiking Developer's Documentation for an overview.
    
    """
    
    class ForwardInfo(object):
        """Request forwarding information.

        The method 'forward()' automatically adds forward information (as an instance of the
        'ForwardInfo' class) to the stack, which may be later inspected through the method
        'forwards()'.

        """
        def __init__(self, module, resolved_path, unresolved_path, **kwargs):
            """Arguments:

              module -- the handler instance to which the request was forwarded
              resolved_path -- sequence of request path items (strings) corresponding to the
                resolved portion of the path at the time of the forward
              unresolved_path -- sequence of request path items (strings) corresponding to the
                unresolved portion of the path at the time of the forward
              kwargs -- any keyword arguments passed to the forward method call.  These arguments
                may be later inspected through the 'arg()' method and make it possible to pass any
                application defined data for later inspection.

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

    _LANG_COOKIE = 'wiking_prefered_language'
    _PANELS_COOKIE = 'wiking_show_panels'
    _UNDEFINED = object()
    
    INFO = 'INFO'
    """Message type constant for informational messages."""
    WARNING = 'WARNING'
    """Message type constant for warning messages."""
    ERROR = 'ERROR'
    """Message type constant for error messages."""
            
    def __init__(self, req, application, **kwargs):
        super(WikingRequest, self).__init__(req, **kwargs)
        self._application = application
        self._forwards = []
        self._messages = []
        self._prefered_languages = self._init_prefered_languages()
        self._module_uri = {}
        self.unresolved_path = list(self.path)

    def _init_options(self):
        options = super(WikingRequest, self)._init_options()
        self._uri_prefix = options.pop('PrefixPath', None)
        return options
    
    def _init_params(self):
        params = super(WikingRequest, self)._init_params()
        if params.has_key('setlang'):
            self._prefered_language = lang = str(params['setlang'])
            del params['setlang']
            self.set_cookie(self._LANG_COOKIE, lang)
        else:
            self._prefered_language = str(self.cookie(self._LANG_COOKIE))
        if params.has_key('hide_panels'):
            self.set_cookie(self._PANELS_COOKIE, 'no')
            self._show_panels = False
        elif params.has_key('show_panels'):
            self.set_cookie(self._PANELS_COOKIE, 'yes')
            self._show_panels = True
        else:
            self._show_panels = self.cookie(self._PANELS_COOKIE) != 'no'
        if params.has_key('__log_in'):
            del params['__log_in']
            login, password = (None, None)
            if params.has_key('login'):
                login = params['login']
                del params['login']
            if params.has_key('password'):
                password = params['password']
                del params['password']
            self._credentials = (login, password)
        else:
            self._credentials = None
        self._user = self._UNDEFINED
        return params

    def _init_path(self, uri):
        if uri.endswith('.rss'):
            self._params['action'] = 'rss'
            uri = uri[:-4]
            if len(uri) > 3 and uri[-3] == '.' and uri[-2:].isalpha():
                self._prefered_language = str(uri[-2:])
                uri = uri[:-3]
        prefix = self._uri_prefix
        if prefix and uri.startswith(prefix):
            uri = uri[len(prefix):]
        return super(WikingRequest, self)._init_path(uri)

    def _init_prefered_languages(self):
        accepted = []
        prefered = self._prefered_language # The prefered language setting from cookie or param.
        for item in self.header('Accept-Language', '').lower().split(','):
            if item:
                x = item.split(';')
                # For now we ignore the country part and recognize just the core languages.
                lang = x[0].split('-')[0]
                if lang == prefered:
                    prefered = None
                    q = 2.0
                elif len(x) == 1:
                    q = 1.0
                elif x[1].startswith('q='):
                    try:
                        q = float(x[1][2:])
                    except ValueError:
                        continue
                else:
                    continue
                if lang not in [l for _q, l in accepted]:
                    accepted.append((q, lang))
        accepted.sort()
        accepted.reverse()
        languages = [lang for q, lang in accepted]
        if prefered:
            languages.insert(0, prefered)
        default = cfg.default_language_by_domain.get(self.server_hostname(current=True),
                                                     cfg.default_language)
        if default and default not in languages:
            languages.append(default)
        return tuple(languages)

    def _cookie_path(self):
        return self._uri_prefix or '/'

    def forward(self, handler, **kwargs):
        """Pass the request on to another handler keeping track of the forwarding history.

        Arguments:
          handler -- 'RequestHandler' instance to handle request.
          kwargs -- all keyword arguments are passed to the 'ForwardInfo' instance created for
            this forward (later available in forward history using the method 'forwards()').
  
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
        """Return the tuple of `ForwardInfo' instances representing the current forwarding stack.

        The items are returned in the order in which the corresponding 'forward()' calls were
        made.  The current 'Application', which normally starts the request handling, is not
        included in this list.

        """
        return tuple(self._forwards)

    def uri_prefix(self):
        """Return the URI prefix as a string or empty string if no prefix is set.

        URI prefix is the fixed part of request URI, which is ignored by Wiking URI resolution
        process.  It may be typically useful when you want to run multiple Wiking applications on
        one virtual host.

        Examples:

          Application 1:
            URI = http://www.yourserver.org/appl1/news
            req.uri() = '/appl1/news'
            req.uri_prefix() = '/appl1'
            req.path = ('news',)

          Application 2:
            URI = http://www.yourserver.org/appl2/xyz
            req.uri() = '/appl2/xyz'
            req.uri_prefix() = '/appl2'
            req.path = ('xyz',)

        It is especially important to respect the prefix when constructing URIs, however this
        feature is now in experimantal state and it is not guaranteeed that it is correctly
        handled by Wiking itself yet.

        In the mod_python environment it can be set by the PythonOption PrefixPath to the value of
        the prefix string and also by setting the appropriate Python interpretter isolation level
        e.g. by the PythonInterpreter directive.

        """
        return self._uri_prefix or ''
        
    def show_panels(self):
        return self._show_panels
    
    def prefered_languages(self):
        """Return a sequence of language codes in the order of client's preference.

        The result is based on the Accept-Language HTTP header, prefered language set previously
        through 'setlang' parameter (stored in a cookie) and default language configured for the
        server (see 'default_language' and 'default_language_by_domain' configuration options).
        
        """
        return self._prefered_languages

    def prefered_language(self, variants=None, raise_error=True):
        """Return the prefered variant from the list of available variants.

        The preference is determined by the order of acceptable languages
        returned by 'prefered_languages()'.

        Arguments:

          variants -- list of language codes of avialable language variants.  If None (default),
            all languages defined by the current Wiking application will be considered.
          
          raise_error -- if false, None is returned if there is no acceptable
            variant in the list.  Otherwise NotAcceptable error is raised.

        """
        if variants is None:
            variants = self._application.languages()
        for lang in self.prefered_languages():
            if lang in variants:
                return lang
        if raise_error:
            raise NotAcceptable(variants)
        else:
            return None

    def credentials(self):
        """Return the login name and password entered in the login form.

        The returned value does not indicate anything about authentication.  The credentials are
        returned even if login was not successful.  The returned value is a pair of strings (login,
        password) or None if no authentication was performed for this request.

        """
        return self._credentials

    def user(self, require=False):
        """Return 'User' instance describing the logged-in user.

        Arguments:

          require -- boolean flag indicating that the user is required to be logged (anonymous
            access not allowed).  If set to true and no user is logged, AuthenticationError will be
            raised (just as a convenience extension).  If false, None is returned, but
            AuthenticationError may still be raised when login credentials are not valid.

        """
        if self._user is self._UNDEFINED:
            # Set to None for the case that authentication raises an exception.
            self._user = None
            # AuthenticationError may be raised if the credentials are invalid.
            self._user = self._application.authenticate(self)
        if require and self._user is None:
            #if session_timed_out:
            #      raise AuthenticationError(_("Session expired. Please log in again."))
            raise AuthenticationError()
        return self._user

    def check_roles(self, *args):
        """Return true, iff the current user belongs to at least one of given roles.

        Arguments may be roles or nested sequences of roles, which will be unpacked.  Roles are
        represented by unique string identifiers as described in documentation of the class
        'Roles'.

        Authentication will be performed only if needed.  In other words, if 'roles' contain
        ANYONE, True will be returned without an attempt to authenticate the user.
        
        """
        roles = []
        for arg in args:
            if isinstance(arg, (list, tuple)):
                roles.extend(arg)
            else:
                roles.append(arg)
        if Roles.ANYONE in roles:
            return True
        user = self.user()
        if user is None:
            return False
        user_roles = user.roles()
        for role in roles:
            if role in user_roles:
                return True
        return False
    
    def application(self):
        """Return the current `Application' instance."""
        return self._application

    def module_uri(self, modname):
        """Return the base URI of given Wiking module (relative to server root)."""
        # Since the uris may be used many times, they are cached at least for the duration of one
        # request.  We cannot cache them over multiple requests, sice there is no way to invalidate
        # them if mapping changes (at least in the multiprocess server invironment).  This method
        # can be implemented by using a global cache if this limitation is overcome in another
        # environment.
        try:
            uri = self._module_uri[modname]
        except KeyError:
            uri = self._module_uri[modname] = self._application.module_uri(modname)
        if uri is not None:
            uri = self.uri_prefix() + uri
        return uri
        
    def message(self, message, type=None):
        """Add a message to the stack.

        Arguments:
          message -- message text as a string.
          type -- message text as one of INFO, WARNING, ERROR constatns of the class.  If None, the
            default is INFO.

        The stacked messages can be later retrieved using the 'messages()' method.

        """
        assert type in (None, self.INFO, self.WARNING, self.ERROR)
        self._messages.append((message, type or self.INFO))

    def messages(self):
        """Return the current stack of messages as a tuple of pairs (MESSAGE, TYPE)."""
        return tuple(self._messages)
    

class User(object):
    """Representation of the logged in user.

    The authentication module returns an instance of this class on successful authentication.  The
    interface defined by this class is used within the framework, but applications are allowed (and
    encouraged) to derive a class with an extended interface used by the application.

    The simplest way of using application-specific extensions is passing an arbitrary object as the
    'data' constructor argument.  This doesn't require deriving a specific 'User' subclass, but may
    be a little cumbersome in some situations.

    """
    
    def __init__(self, login, uid=None, name=None, roles=(), email=None, password=None, 
                 password_expiration=None, uri=None, data=None, lang='en',
                 organization_id=None, organization=None):
        """Initialize the instance.

        Arguments:

          login -- user's login name as a string
          uid -- user identifier used for ownership determination (see role OWNER)
          name -- visible name as a string (login is used if None)
          roles -- sequence of user roles as unique string identifiers (see 'Roles')
          email -- e-mail address as a string
          password -- user's expected authentication password or None if password authentication is
            not allowed.  The login password will be checked against this value for authentication
            to succeed.
          password_expiration -- password expiration date as a Python 'date' instance or None
          uri -- user's profile URI or None
          data -- application specific data
          organization_id -- id of the user's organization as an Integer
          organization -- name of the user's organization as a string or
            unicode; or 'None' if the user doesn't belong to any organization
          lang -- code of the user's preferred language

        Please note, that password expiration date has currently no impact on the authentication
        process.  It will just be displayed in the login panel, if defined.

        """
        assert isinstance(login, (unicode, str))
        assert name is None or isinstance(name, (unicode, str))
        assert isinstance(roles, (tuple, list))
        self._login = login
        self._uid = uid or login
        self._name = name or login
        self._roles = tuple(roles)
        self._email = email
        self._password = password
        self._password_expiration = password_expiration
        self._uri = uri
        self._data = data
        self._organization_id = organization_id
        if organization is not None:
            organization = unicode(organization)
        self._organization = organization
        self._lang = lang
        self._auto_authentication = False
        self._authentication_method = None
        
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
        """Return valid user's roles as a tuple of unique string identifiers (see 'Roles')."""
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

    def uri(self):
        """Return the URI of user's profile."""
        return self._uri

    def data(self):
        """Return application specific data passed to the constructor."""
        return self._data

    def organization_id(self):
        """Return user's organization id as an integer.

        If the user doesn't belong to any organization, return 'None'.

        """
        return self._organization_id

    def organization(self):
        """Return user's organization as a unicode.

        If the user doesn't belong to any organization, return 'None'.

        """
        return self._organization

    def lang(self):
        """Return code of the user's preferred language."""
        return self._lang

    def auto_authentication(self):
        """Return true iff the user was authenticated automatically."""
        return self._auto_authentication

    def authentication_method(self):
        """Return authentication method of the user.

        It may be one of the string 'password' and 'certificate'.  If the user
        wasn't authenticated, return 'None'.

        """
        return self._authentication_method
    
    def set_authentication_parameters(self, method=None, auto=None):
        """Set authentication parameters of the user instance.

        Arguments:

          method -- authentication method used in the current request, one of
            the strings 'password', 'certificate'
          auto -- whether the user was initially authenticated
            non-interactively, e.g. by using a certificate; boolean

        If any of the arguments is unspecified, the corresponding parameter
        retains its value.
        
        """
        # TODO: Wouldn't it be possible to pass these parameters to the constructor as all other
        # parameters?
        if method is not None:
            assert method in ('password', 'certificate')
            self._authentication_method = method
        if auto is not None:
            assert isinstance(auto, bool)
            self._auto_authentication = auto
        
    
class Roles(object):
    """Predefined static user roles.

    Wiking applications may use the roles defined here, extend this class to define additional
    static roles or use application specific dynamic roles.  In any case, all valid roles are
    represented by string identifiers and the application must take care to use unique identifiers
    for all its roles.

    Static roles are defined as public constants of this class below.

    """
    ANYONE = 'ANYONE'
    """Anyone, even a user who is not logged-in."""
    USER = 'USER'
    """Any logged-in user who is at least enabled."""
    ADMIN = 'ADMIN'
    """Administrator (usually with unlimited privileges)."""
    OWNER = 'OWNER'
    """The owner of the item being operated.
    
    Wiking application is responsible for providing owner checking in its authorization checking
    routines (it it wants to make use of this role).  Wiking CMS, for example, implements this
    through the method `PytisModule.check_owner()' for pytis based modules (each record may have
    its owner).

    """

    @classmethod
    def check(cls, req, roles):
        """DEPRECATED!  Use 'Request.check_roles()' instead."""
        if cls.ANYONE in roles:
            return True
        user = req.user()
        if user is None:
            return False
        for role in roles:
            if role in user.roles():
                return True
        return False
