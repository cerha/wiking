# Copyright (C) 2010, 2011 Brailcom, o.p.s.
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

import wsgiref.util, wsgiref.headers, cgi, httplib
import wiking


class WsgiFileUpload(wiking.Request):
    # TODO: This is just copied from mod_python_interface.  Needs to be implemented for WSGI!
    def __init__(self, field, encoding):
        self._field = field
        self._filename = re.split(r'[\\/:]', unicode(field.filename, encoding))[-1]
    def file(self):
        return self._field.file
    def filename(self):
        return self._filename
    def type(self):
        return self._field.type

    
class WsgiRequest(wiking.Request):
    """Wiking server interface implementation for WSGI.

    Implements the 'wiking.ServerInterface' API.

    """
    class Generator(object):
        pass
        
    def __init__(self, environ, start_response, encoding='utf-8'):
        """Initializes the request with WSGI parameters.

        environ, start_response -- same-named arguments to the WSGI application
            object callable, as per WSGI spec (PEP 333)

        """
        self._environ = environ
        self._start_response = start_response
        self._response_headers_storage = []
        self._response_headers = wsgiref.headers.Headers(self._response_headers_storage)
        self._params = self._init_params(encoding)
        self._response_started = False
        self._data = []
        self._uri = unicode(environ['PATH_INFO'], encoding)
        super(WsgiRequest, self).__init__(encoding=encoding)

    def _init_params(self, encoding):
        def init_value(value):
            if isinstance(value, (tuple, list)):
                return tuple([init_value(v) for v in value])
            elif value.file:
                return WsgiFileUpload(value, encoding)
            else:
                return unicode(value.value, encoding)
        fields = cgi.FieldStorage(fp=self._environ['wsgi.input'],
                                  environ=self._environ)
        return dict([(k, init_value(fields[k])) for k in fields])

    def uri(self):
        return self._uri

    def unparsed_uri(self):
        return self._environ['REQUEST_URI']
        
    def param(self, name, default=None):
        return self._params.get(name, default)

    def params(self):
        return self._params.keys()

    def has_param(self, name):
        return name in self._params

    def set_param(self, name, value):
        if value is None:
            if name in self._params:
                del self._params[name]
        else:
            self._params[name] = value

    def header(self, name, default=None):
        if name == 'Content-Type':
            environ_name = 'CONTENT_TYPE'
        elif name == 'Content-Length':
            environ_name = 'CONTENT_LENGTH'
        else:
            environ_name = 'HTTP_' + name.replace('-', '_').upper()
        return self._environ.get(environ_name, default)

    def set_header(self, name, value, **params):
        # See wsgiref.headers.Headers.add_header for the documentation.
        self._response_headers.add_header(name, value.encode(self._encoding), **params)

    def port(self):
        return self._environ['SERVER_PORT']
        
    def https(self):
        #TODO: what about self._environ['HTTPS']? isn't it by definition correct, if present?
        return self.port() == wiking.cfg.https_port

    def remote_host(self):
        return self._environ.get('REMOTE_HOST', self._environ.get('REMOTE_ADDR'))

    def server_hostname(self, current=False):
        if current:
            return self._environ.get(self.header('Host'), self._environ['SERVER_NAME'])
        else:
            return self._environ['SERVER_NAME']

    def start_http_response(self, status_code):
        if True: #not self._response_started:
            self._response_started = True
            response = '%d %s' % (status_code, httplib.responses[status_code])
            self._start_response(response, self._response_headers_storage)
        else:
            raise RuntimeError("start_http_response() can only be called once!")

    def write(self, data):
        # TODO: send data to wsgi directly as they are written!
        self._data.append(data)

    def option(self, name, default=None):
        return self._environ.get('wiking.'+ name, default)

    def response(self, handler):
        """This method is internal to the WSGI module.

        It should never be used within Wiking applications.

        """
        handler.handle(self)
        # TODO: yield data immediately as write() is called.
        for chunk in self._data:
            yield chunk


class WsgiEntryPoint(object):
    """WSGI entry point.

    This class implements a WSGI specific wrapper of 'wiking.Handler'.

    An instance of this class is created below to serve as mod_wsgi entry
    point.  The instance is callable and will be called to serve the request.
    
    """
    def __init__(self):
        self._handler = None

    def __call__(self, environ, start_response):
        if self._handler is None:
            # Initialization is postponed until the first request, since we
            # need information from the environment to initialize the the
            # handler instance.
            options = dict([(k[7:], v) for k, v in environ.items() if k.startswith('wiking.')])
            self._handler = wiking.Handler(environ['SERVER_NAME'], None, options)
        req = WsgiRequest(environ, start_response)
        return req.response(self._handler)
        

application = WsgiEntryPoint()
