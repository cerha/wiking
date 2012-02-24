# Copyright (C) 2010, 2011, 2012 Brailcom, o.p.s.
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
        self._response_data = []
        self._uri = unicode(environ['SCRIPT_NAME'] + environ['PATH_INFO'], encoding)
        super(WsgiRequest, self).__init__(encoding=encoding)
        #if not self.uri().startswith('/_'):
        #    wiking.debug("============== %s ==============" % self.uri())
        #    for key, val in sorted(environ.items()):
        #        wiking.debug(key, val)

    def _init_params(self, encoding):
        def init_value(value):
            if isinstance(value, (tuple, list)):
                return tuple([init_value(v) for v in value])
            elif value.filename:
                return wiking.FileUpload(value, encoding)
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
        return int(self._environ['SERVER_PORT'])
        
    def https(self):
        return self._environ['wsgi.url_scheme'] == 'https'

    def remote_host(self):
        return self._environ.get('REMOTE_HOST', self._environ.get('REMOTE_ADDR'))

    def server_hostname(self):
        return self._environ.get(self.header('Host'), self._environ['SERVER_NAME'])

    def primary_server_hostname(self):
        # PEP http://www.python.org/dev/peps/pep-3333/ is not very clear on
        # what SERVER_NAME should exactly contain and we don't know of any
        # other method how to retrieve the unique server name (as descrined
        # in the docstring of this method in the parent class) under WSGI.
        # So at least under Apache/mod_wsgi, it is necessary to set the
        # environment variable 'wiking.server_hostname' according the
        # ServerName directive whenever there is one or more ServerAlias
        # directives because SERVER_NAME doesn't contain what we need.
        return None

    def start_http_response(self, status_code):
        if True: #not self._response_started:
            self._response_started = True
            response = '%d %s' % (status_code, httplib.responses[status_code])
            self._start_response(response, self._response_headers_storage)
        else:
            raise RuntimeError("start_http_response() can only be called once!")

    def write(self, data):
        # This works fine for ordinary pages, but it doesn't allow streaming
        # (it will work, but the whole stream must be read into memory and sent
        # in one chunk).  Implementing the WSGI generator interface on top of
        # Wiking's imperative approach with req.write() would involve a
        # multithreaded queue.  It seems better to add support for returning a
        # generator instance from wiking.Handler.handle().  This would work
        # seamlesly with WSGI and would be easy to implement for mod_python.
        # The Wiking applications which need streaming would need to be changed
        # to use generators instead of req.write() than, but there's not so
        # much code like that (one example is wiking.Request.send_file()).
        if isinstance(data, buffer):
            # WSGI doesn't accept buffer, while mod_python's write() does so
            # this is necessary for backwards compatibility.  It would be
            # probably good, however, to deprecate passing python buffer
            # instances to wiking.Request.write().
            data = str(data)
        self._response_data.append(data)

    def option(self, name, default=None):
        return self._environ.get('wiking.'+ name, default)

    def response_data(self):
        """This method is internal to the WSGI module.
        
        It should never be used within Wiking applications.
        
        """
        return self._response_data

class WsgiEntryPoint(object):
    """WSGI entry point.

    This class implements a WSGI specific wrapper of 'wiking.Handler'.

    An instance of this class is created below to serve as mod_wsgi entry
    point.  The instance is callable and will be called to serve the request.
    
    """
    def __init__(self):
        self._handler = None

    def __call__(self, environ, start_response):
        req = WsgiRequest(environ, start_response)
        handler = self._handler
        if handler is None:
            # Initialization is postponed until the first request, since we
            # need information from the environment to initialize the the
            # handler instance.
            handler = self._handler = wiking.Handler(req)
        handler.handle(req)
        for chunk in req.response_data():
            yield chunk


application = WsgiEntryPoint()
