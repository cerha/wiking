# Copyright (C) 2010, 2011, 2012, 2013, 2014 Brailcom, o.p.s.
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

import cgi
import httplib
import os
import wsgiref.util
import wsgiref.headers
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
        # It is important to avoid possible exceptions (such as UnicodeDecodeError)
        # here as they would escape Wiking's exception handling.  Thus further
        # sensitive processing should be done later on demand when instance methods
        # are called.
        self._environ = environ
        self._start_response = start_response
        self._uri = None
        self._params = {}
        self._raw_params = cgi.FieldStorage(fp=environ['wsgi.input'], environ=environ)
        self._unset_params = []
        self._response_headers_storage = []
        self._response_headers = wsgiref.headers.Headers(self._response_headers_storage)
        self._response_started = False
        super(WsgiRequest, self).__init__(encoding=encoding)

    def uri(self):
        if self._uri is None:
            # Not done in constructor (see the constructor comment).
            raw_uri = self._environ.get('SCRIPT_NAME', '') + self._environ['PATH_INFO']
            self._uri = unicode(raw_uri, self._encoding)
        return self._uri

    def unparsed_uri(self):
        return self._environ['REQUEST_URI']
        
    def param(self, name, default=None):
        def param_value(value):
            # Value processing not done in constructor (see the constructor comment).
            if isinstance(value, (tuple, list)):
                return tuple([param_value(v) for v in value])
            elif value.filename == '' and value.value == '':
                # Empty file upload fields give this strange combination...
                return None
            elif value.filename:
                return wiking.FileUpload(value, self._encoding)
            else:
                return unicode(value.value, self._encoding)
                # TODO: return BadRequest instead of InternalServerError? Is it always
                # browser's fault if it doesn't encode the request properly?
                #except UnicodeDecodeError:
                #    raise wiking.BadRequest(_("Request parameters not encoded properly into %s.",
                #                              self._encoding))
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
        return tuple(k for k in self._raw_params.keys() if k not in self._unset_params)

    def has_param(self, name):
        return name in self._raw_params and name not in self._unset_params

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

    def option(self, name, default=None):
        return self._environ.get('wiking.' + name, default)


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
        return handler.handle(req)


application = WsgiEntryPoint()

# Hack to allow wsgi shell access, any better solution is welcome.

_wsgi_shell_config_file = os.path.join(os.getenv('HOME'), 'ispyd.ini')
if os.access(_wsgi_shell_config_file, os.R_OK):
    from ispyd.manager import ShellManager
    shell_manager = ShellManager(_wsgi_shell_config_file)
    from ispyd.plugins.wsgi import WSGIApplicationWrapper
    application = WSGIApplicationWrapper(application)
