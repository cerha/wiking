# -*- coding: utf-8 -*-
#
# Copyright (C) 2010-2016 OUI Technology Ltd.
# Copyright (C) 2019-2021, 2025 Tomáš Cerha <t.cerha@gmail.com>
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

import cgi
import os
import wsgiref.util
import wsgiref.headers
import wiking

import http.client
import urllib.parse


class WsgiRequest(wiking.Request):
    """Wiking server interface implementation for WSGI.

    Implements the 'wiking.ServerInterface' API.

    """
    class Generator:
        pass

    def __init__(self, environ, start_response, encoding='utf-8'):
        """Initializes the request with WSGI parameters.

        environ, start_response -- same-named arguments to the WSGI application
            object callable, as per WSGI spec (PEP 333)

        """
        # It is important to avoid possible exceptions (such as UnicodeDecodeError)
        # here as they would escape Wiking's exception handling.  Thus further
        # sensitive processing should be done later on demand when instance methods
        # are called.
        self._environ = environ
        self._start_response = start_response
        self._root = self._environ.get('SCRIPT_NAME')
        self._uri = self._environ['PATH_INFO']
        self._params = {}
        if self.method() == 'OPTIONS':
            self._raw_params = {}
        else:
            self._raw_params = cgi.FieldStorage(fp=environ['wsgi.input'], environ=environ,
                                                keep_blank_values=True)
        self._unset_params = []
        self._response_headers_storage = []
        self._response_headers = wsgiref.headers.Headers(self._response_headers_storage)
        super(WsgiRequest, self).__init__(encoding=encoding)

    def root(self):
        return self._root

    def uri(self):
        return self._uri

    def unparsed_uri(self):
        uri = wsgiref.util.request_uri(self._environ)
        if uri:
            uri = urllib.parse.urlunsplit(('', '',) + urllib.parse.urlsplit(uri)[2:])
        return uri

    def method(self):
        return self._environ['REQUEST_METHOD']

    def param(self, name, default=None):
        def param_value(value):
            # Value processing not done in constructor (see the constructor comment).
            if isinstance(value, (tuple, list)):
                return tuple(param_value(v) for v in value)
            elif value.filename == '' and value.value == b'':
                # Empty file upload fields give this strange combination...
                return None
            elif value.filename:
                return wiking.FileUpload(value, self._encoding)
            else:
                return value.value
        try:
            return self._params[name]
        except KeyError:
            if name in self._unset_params:
                return default
            try:
                raw_value = self._raw_params[name]
            except KeyError:
                return default
            self._params[name] = value = param_value(raw_value)
            return value

    def params(self):
        return tuple(set(self._raw_params).union(set(self._params)) - set(self._unset_params))

    def set_param(self, name, value):
        if value is None:
            if name in self._params:
                del self._params[name]
            if name not in self._unset_params:
                self._unset_params.append(name)
        else:
            if name in self._unset_params:
                self._unset_params.remove(name)
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
        def encode(string):
            # Hack: Non latin-1 characters will lead to
            # "TypeError: http header must be encodable in latin1"
            # when start_http_response() is called.  There doesn't seem to be
            # any official documentation how this should be solved correctly,
            # but this hack seems to work.
            return string.encode(self._encoding).decode('latin1')
        # See wsgiref.headers.Headers.add_header for the documentation.
        self._response_headers.add_header(name, encode(value), **{k: encode(v) for k, v in params.items()})

    def port(self):
        port = self._environ['SERVER_PORT']
        if not port:
            return None
        return int(port)

    def https(self):
        return self._environ['wsgi.url_scheme'] == 'https'

    def remote_host(self):
        return self._environ.get('REMOTE_HOST', self._environ.get('REMOTE_ADDR'))

    def server_hostname(self):
        return self.header('Host') or self._environ['SERVER_NAME']

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
        self._start_response(
            '%d %s' % (status_code, http.client.responses[status_code]),
            self._response_headers_storage
        )

    def option(self, name, default=None):
        return self._environ.get('wiking.' + name, default)


class WsgiEntryPoint:
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
        return handler.handle(req)


application = WsgiEntryPoint()

# Hack to allow wsgi shell access, any better solution is welcome.
_wsgi_shell_config_file = os.path.expanduser('~/ispyd.ini')
if os.access(_wsgi_shell_config_file, os.R_OK):
    from ispyd.manager import ShellManager
    shell_manager = ShellManager(_wsgi_shell_config_file)
    from ispyd.plugins.wsgi import WSGIApplicationWrapper
    application = WSGIApplicationWrapper(application)
