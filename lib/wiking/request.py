# Copyright (C) 2006, 2007, 2008 Brailcom, o.p.s.
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
        cookies = Cookie.SimpleCookie(self.header('Cookie'))
        if cookies.has_key(name):
            return cookies[name].value
        else:
            return default
        
    def set_cookie(self, name, value, expires=None, secure=False):
        c = Cookie.SimpleCookie()
        c[name] = value
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

    def server_hostname(self):
        return self._req.server.server_hostname

    def server_uri(self, force_https=False):
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
        result = protocol + '://'+ self._req.server.server_hostname
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
        if content_type in ("text/html", "application/xml", "text/css") \
               and isinstance(data, unicode):
            content_type += "; charset=%s" % self._encoding
            #data = self._UNIX_NEWLINE.sub("\r\n", data)
            data = data.encode(self._encoding)
        self.send_http_header(content_type, len(data))
        self.write(data)
        return apache.OK

    def serve_file(self, filename, content_type):
        """Send the contents of given file to the remote host.

        Arguments:
          filename -- full path to the file
          content_type -- Content-Type header as a string

        'NotFound' exception will be raised if the file does not exist.

        Important note: The file size is read in advance to determine the Content-Lenght header.
        If the file is changed before it gets sent, the result may be incorrect.
        
        """
        try:
            size = os.stat(filename).st_size
        except OSError:
            raise NotFound
        self.send_http_header(content_type, size)
        f = file(filename)
        try:
            while True:
                # Read the file in 0.5MB chunks.
                data = f.read(524288)
                if not data:
                    break
                self.write(data)
        finally:
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
    """Wiking application specific request object."""
    
    class ForwardInfo(object):
        """Request forwarding information.

        The method 'WikingRequest.forward()' automatically adds forward information to the stack,
        which may be later inspected through the method 'WikingRequest.forwards()'.  Each item on
        this stack is an instance of this class.  The constructor arguments are supplied as
        follows:

          module -- the handler instance to which the request was forwarded
          uri -- uri corresponding to the resolved portion of the path (at the time of the forward)
          kwargs -- any keyword arguments passed to the forward method call.  These arguments may
            be later inspected through the 'args()' method and make it possible to pass any
            application defined data for later inspection.

        """
        
        def __init__(self, module, uri, **kwargs):
            self._module = module
            self._uri = uri
            self._data = kwargs
            
        def module(self):
            """Return the 'module' passed to the constructor."""
            return self._module
        
        def uri(self):
            """Return the 'uri' passed to the constructor."""
            return self._uri
        
        def arg(self, name):
            """Return the value of keyword argument 'name' passed to the constructor or None."""
            try:
                return self._data[name]
            except KeyError:
                return None
            
    _LANG_COOKIE = 'wiking_prefered_language'
    _PANELS_COOKIE = 'wiking_show_panels'
    _UNDEFINED = object()
    
    def __init__(self, req, application, **kwargs):
        super(WikingRequest, self).__init__(req, **kwargs)
        self._application = application
        self._forwards = []
        self.unresolved_path = list(self.path)

    def _init_params(self):
        params = super(WikingRequest, self)._init_params()
        if params.has_key('setlang'):
            self._prefered_language = lang = str(params['setlang'])
            del params['setlang']
            # Expires in 2 years (in seconds)
            self.set_cookie(self._LANG_COOKIE, lang, expires=730*DAY)
        else:
            self._prefered_language = self.cookie(self._LANG_COOKIE)
        if params.has_key('hide_panels'):
            self.set_cookie(self._PANELS_COOKIE, 'no', expires=730*DAY)
            self._show_panels = False
        elif params.has_key('show_panels'):
            self.set_cookie(self._PANELS_COOKIE, 'yes', expires=730*DAY)
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
                self._params['lang'] = uri[-2:]
                uri = uri[:-3]
        if self._options.has_key('PrefixPath'):
            self._uri_prefix = prefix = self._options['PrefixPath']
            x = uri
            if uri.startswith(prefix):
                uri = uri[len(prefix):]
        else:
            self._uri_prefix = None
        return super(WikingRequest, self)._init_path(uri)

    def _cookie_path(self):
        return self._uri_prefix or '/'

    def forward(self, handler, **kwargs):
        """Pass the request on to another handler keeping track of the handlers.

        Adds the module to the list of used handlers and returns the result of calling
        'handler.handle(req)'.  The 'handler' must be a 'RequestHandler' instance.

        The list of used handlers can be retrieved using the 'handlers()' method.

        """
        if self.unresolved_path:
            path = self.path[:-len(self.unresolved_path)]
        else:
            path = self.path
        uri = '/' + '/'.join(path)
        self._forwards.append(self.ForwardInfo(handler, uri, **kwargs))
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
        return self._uri_prefix or ''
        
    def show_panels(self):
        return self._show_panels
    
    def prefered_languages(self):
        """Return a sequence of languages acceptable by the client.

        The language codes are returned in the order of preference.
        
        """
        try:
            return self._prefered_languages
        except AttributeError:
            accepted = []
            prefered = self._prefered_language
            for item in self.header('Accept-Language', '').lower().split(','):
                if not item:
                    continue
                x = item.split(';')
                lang = x[0]
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
                accepted.append((q, lang))
            accepted.sort()
            accepted.reverse()
            languages = [l for q, l in accepted]
            if prefered:
                languages = [prefered] + languages
            default = 'en' #config.default_language
            if default and default not in languages:
                languages += [default]
            self._prefered_languages = tuple(languages)
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
        for l in self.prefered_languages():
            if l in variants:
                return l
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
    
    def application(self):
        """Return the current `Application' instance."""
        return self._application
        

class User(object):
    """Representation of the logged in user.

    The authentication module returns an instance of this class on successful authentication.  The
    interface defined by this class is used within the framework, but application is allowed to
    append any application specific data to the instance by passing the 'data' argument to the
    constructor.

    """
    
    def __init__(self, login, uid=None, name=None, roles=(), email=None, data=None,
                 passwd_expiration=None, uri=None, organization_id=None, organization=None):
        """Initialize the instance.

        Arguments:

          login -- user's login name as a string
          uid -- user identifier used for ownership determination (see role OWNER)
          name -- visible name as a string (login is used if None)
          roles -- sequence of user roles as 'Roles' constants
          email -- e-mail address as a string
          data -- application specific data
          passwd_expiration -- password expiration date as a Python 'date' instance or None
          uri -- user's profile URI or None
          organization_id -- id of the user's organization as an Integer
          organization -- name of the user's organization as a string or
            unicode; or 'None' if the user doesn't belong to any organization

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
        self._data = data
        self._passwd_expiration = passwd_expiration
        self._uri = uri
        self._organization_id = organization_id
        if organization is not None:
            organization = unicode(organization)
        self._organization = organization
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
        """Return valid user's roles as a tuple of 'Roles' constants."""
        return self._roles
    
    def email(self):
        """Return user's e-mail address as a string or None if not defined."""
        return self._email
    
    def data(self):
        """Return application specific data passed to the constructor."""
        return self._data

    def passwd_expiration(self):
        """Return password expiration date as a Python 'date' instance or None."""
        return self._passwd_expiration

    def uri(self):
        """Return the URI of user's profile."""
        return self._uri

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
        if method is not None:
            assert method in ('password', 'certificate')
            self._authentication_method = method
        if auto is not None:
            assert isinstance(auto, bool)
            self._auto_authentication = auto
        
    
class Roles(object):
    """Static definition of available user roles."""
    ANYONE = 'ANYONE'
    """Anyone, even a user who is not logged-in."""
    USER = 'USER'
    """Any logged-in user who is at least enabled."""
    OWNER = 'OWNER'
    """The owner of the item being operated."""
    ADMIN = 'ADMIN'
    """Administrator (usually has unlimited privileges)."""

    @classmethod
    def check(cls, req, roles):
        """Check, whether the logged in user belongs at least to one of given 'roles'.

        Arguments:

          req -- request object used for obtaining the current user (if needed)
          roles -- sequence of allowed user roles

        Returns True if the user belongs at least to one of given roles and False otherwise.

        Authentication will be performed only if needed.  In other words, if 'roles' contain
        ANYONE, True will be returned without an attempt to authenticate the user.

        """
        if cls.ANYONE in roles:
            return True
        user = req.user()
        if user is None:
            return False
        for role in roles:
            if role in user.roles():
                return True
        return False
