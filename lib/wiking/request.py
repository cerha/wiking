# Copyright (C) 2006, 2007 Brailcom, o.p.s.
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
    
import random
import Cookie

_ = lcg.TranslatableTextFactory('wiking')

DAY = 86400

class FileUpload(pytis.web.FileUpload):
    """Mod_python specific implementation of pytis FileUpload interface."""
    def __init__(self, field):
        self._field = field
    def file(self):
        return self._field.file
    def filename(self):
        return self._field.filename
    def type(self):
        return self._field.type


class Request(pytis.web.Request):
    """Mod_python request wrapper implementing the pytis request interface."""
    
    _UNIX_NEWLINE = re.compile("(?<!\r)\n")
    
    def __init__(self, req, encoding='utf-8'):
        self._req = req
        self._encoding = encoding
        # Store request data in real dictionaries.
        self.params = self._init_params()
        self.uri = self._init_uri()
        self.path = [item for item in self.uri.split('/')[1:] if item]

    def _init_params(self):
        def init_value(value):
            if isinstance(value, (tuple, list)):
                return tuple([init_value(v) for v in value])
            elif isinstance(value, mod_python.util.Field):
                return FileUpload(value)
            else:
                return unicode(value, self._encoding)
        fields = mod_python.util.FieldStorage(self._req)
        return dict([(k, init_value(fields[k])) for k in fields.keys()])

    def _init_uri(self):
        return self._req.uri

    # Methods implementing the pytis Request interface:
    
    def has_param(self, name):
        return self.params.has_key(name)
        
    def param(self, name, default=None):
        return self.params.get(name, default)
        
    def cookie(self, name, default=None):
        cookies = Cookie.SimpleCookie(self.header('Cookie'))
        if cookies.has_key(name):
            return cookies[name].value
        else:
            return default
        
    def set_cookie(self, name, value, expires=None):
        c = Cookie.SimpleCookie()
        c[name] = value
        c[name]['domain'] = self._req.server.server_hostname
        c[name]['path'] = '/'
        if expires is not None:
            c[name]['expires'] = expires
        cookie = c[name].OutputString()
        self._req.headers_out.add("Set-Cookie", cookie)

    # Additional methods:

    def options(self):
        options = self._req.get_options()
        return dict([(o, options[o]) for o in options.keys()])

    def header(self, name, default=None):
        try:
            return self._req.headers_in[name]
        except KeyError:
            return default

    def set_header(self, name, value):
        self._req.headers_out.add(name, value)
        
    def remote_host(self):
        return self._req.get_remote_host()

    def server_hostname(self):
        return self._req.server.server_hostname
        
    def set_status(self, status):
        self._req.status = status
        
    def result(self, data, content_type="text/html"):
        if content_type in ("text/html", "application/xml", "text/css") \
               and isinstance(data, unicode):
            content_type += "; charset=%s" % self._encoding
            #data = self._UNIX_NEWLINE.sub("\r\n", data)
            data = data.encode(self._encoding)
        self._req.content_type = content_type
        self._req.send_http_header()
        self._req.write(data)
        return apache.OK

    def https(self):
        """Return true if https is on."""
        port = self._req.connection.local_addr[1]
        return port in cfg.https_ports
    
    def abs_uri(self, port=None):
        if port is None:
            port = self._req.connection.local_addr[1]
        if port in cfg.https_ports:
            protocol = 'https://'
            default_port = 443
        else:
            protocol = 'http://'
            default_port = 80            
        return protocol + self._req.server.server_hostname + \
               (port and port != default_port and ':'+ str(port) or '') + \
               self.uri
    
    def error(self, message):
        self._req.content_type = "text/html; charset=UTF-8"
        self._req.send_http_header()
        self._req.status = apache.HTTP_INTERNAL_SERVER_ERROR
        from xml.sax.saxutils import escape
        self._req.write("<html><head>"
                        "<title>501 Internal Server Error</title>"
                        "</head>"
                        "<body><h1>Internal Server Error</h1>"
                        "<p>The server was unable to complete your request. "
                        "Please inform the server administrator, %s if the "
                        "problem persists.</p>"
                        "The error message was:"
                        "<pre>" % self._req.server.server_admin + escape(message)+\
                        "</pre></body></html>")
        return apache.OK

    def redirect(self, uri, permanent=False):
        self._req.content_type = "text/html"
        self._req.send_http_header()
        self._req.status = permanent and apache.HTTP_MOVED_PERMANENTLY or \
                           apache.HTTP_MOVED_TEMPORARILY
        self.set_header('Location', uri)
        self._req.write("<html><head><title>Redirected</title></head>"
                        "<body>Your request has been redirected to "
                        "<a href='"+uri+"'>"+uri+"</a>.</body></html>")
        return apache.OK


class WikingRequest(Request):
    """Wiking specific methods for the request object."""
    _LANG_COOKIE = 'wiking_prefered_language'
    _PANELS_COOKIE = 'wiking_show_panels'
    _UNDEFINED = object()

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

    def _init_uri(self):
        uri = super(WikingRequest, self)._init_uri()
        if uri.endswith('.rss'):
            self.params['action'] = 'rss'
            uri = uri[:-4]
            if len(uri) > 3 and uri[-3] == '.' and uri[-2:].isalpha():
                self.params['lang'] = uri[-2:]
                uri = uri[:-3]
        return uri
    
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

    def prefered_language(self, variants, raise_error=True):
        """Return the prefered variant from the list of available variants.

        The preference is determined by the order of acceptable languages
        returned by 'prefered_languages()'.

        Arguments:

          variants -- list of language codes of avialable language variants
          raise_error -- if false, None is returned if there is no acceptable
            variant in the list.  Otherwise NotAcceptable error is raised.

        """
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

    def set_auth_module(self, module):
        """Set the module used for authentication."""
        self._auth_module = module
        
    def user(self, raise_error=False):
        """Return the record describing the logged-in user.

        Arguments:

          raise_error -- boolean flag indicating that the user is required to be logged (anonymous
            access forbidden).  If set to true and no user is logged, AuthenticationError will be
            raised.  If false, None is returned, but AuthenticationError may still be raised when
            login credentials are not valid.

        This method may not be used without a previous call to 'set_auth_module()'.  The returned
        record is the user record obtained from this module.

        """
        if self._user is self._UNDEFINED:
            # Set to None for the case that authentication raises an exception.
            self._user = None
            # AuthenticationError may be raised if the credentials are invalid.
            self._user = self._auth_module.authenticate(self)
        if raise_error and self._user is None:
            #if session_timed_out:
            #      raise AuthenticationError(_("Session expired. Please log in again."))
            raise AuthenticationError()
        return self._user
    
