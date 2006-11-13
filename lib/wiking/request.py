# Copyright (C) 2006 Tomas Cerha <cerha@brailcom.org>
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

if sys.modules.has_key('mod_python'):
    from mod_python import apache
    import mod_python.util
else:
    # This hack makes this module importable even if mod_python is not loaded.
    class Apache(object):
        OK = 1
    apache = Apache()
    
import Cookie

class Request(object):
    """Generic convenience wrapper for the Apache request object."""
    OK = apache.OK
    _UNIX_NEWLINE = re.compile("(?<!\r)\n")
    
    def __init__(self, req, encoding='utf-8'):
        self._req = req
        self._encoding = encoding
        # Store request data in real dictionaries.
        self.uri = req.uri
        self.get_remote_host = req.get_remote_host
        self.server = req.server
        self.params = self._init_params()
        options = req.get_options()
        self.options = dict([(o, options[o]) for o in options.keys()])

    def _init_params(self):
        fields = mod_python.util.FieldStorage(self._req)
        return dict([(k, unicode(fields[k], self._encoding))
                     for k in fields.keys()])
        
    def param(self, name, default=None):
        return self.params.get(name, default)
        
    def header(self, name, default=None):
        try:
            return self._req.headers_in[name]
        except KeyError:
            return default

    def get_cookie(self, name, default=None):
        cookies = Cookie.SimpleCookie(self.header('Cookie'))
        if cookies.has_key(name):
            return cookies[name].value
        else:
            return default
        
    def set_cookie(self, name, value, expires=None):
        c = Cookie.SimpleCookie()
        c[name] = value
        c[name]['domain'] = self.server.server_hostname
        c[name]['path'] = '/'
        if expires is not None:
            c[name]['expires'] = expires
        cookie = c[name].OutputString()
        self._req.headers_out.add("Set-Cookie", cookie)

    def set_status(self, status):
        self._req.status = status
        
    def result(self, data, content_type="text/html"):
        if content_type in ("text/html", "application/xml", "text/css"):
            content_type += "; charset=%s" % self._encoding
            #data = self._UNIX_NEWLINE.sub("\r\n", data)
            data = data.encode(self._encoding)
        self._req.content_type = content_type
        self._req.send_http_header()
        self._req.write(data)
        return apache.OK

    def abs_uri(self):
        port = self._req.connection.local_addr[1]
        return 'http://' + self.server.server_hostname + \
               (port and port != 80 and ':'+ str(port) or '') + self.uri
    
    def error(self, message):
        self._req.content_type = "text/html; charset=UTF-8"
        self._req.send_http_header()
        self._req.status = apache.HTTP_INTERNAL_SERVER_ERROR
        from xml.sax.saxutils import escape
        self._req.write("<html><head>"
                        "<title>501 Internal Server Error</title>"
                        "</head>"
                        "<h1>Internal Server Error</h1>"
                        "<p>The server was unable to complete your request. "
                        "Please inform the server administrator, %s if the "
                        "problem persists.</p>"
                        "The error message was:"
                        "<pre>" % self.server.server_admin + escape(message) +\
                        "</pre></html>")
        return apache.OK


class WikingRequest(Request):
    """Wiking specific methods for the request object."""
    _LANG_COOKIE = 'wiking_prefered_language'

    def __init__(self, *args, **kwargs):
        super(WikingRequest, self).__init__(*args, **kwargs)
        path = self.uri.split('/')[1:]
        self.wmi = path and path[0] == 'wmi'
    
    def _init_params(self):
        params = super(WikingRequest, self)._init_params()
        lang = params.has_key('lang') and str(params['lang']) or None
        if lang and params.has_key('keep_language'):
            del params['keep_language']
            # Expires in 2 years (in seconds)
            self.set_cookie(self._LANG_COOKIE, lang, expires=63072000)
            self._prefered_language = lang
        else:
            self._prefered_language = lang or self.get_cookie(self._LANG_COOKIE)
        return params

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
        for l in self.prefered_languages():
            if l in variants:
                return l
        if raise_error:
            raise NotAcceptable(variants)
        else:
            return None
        
