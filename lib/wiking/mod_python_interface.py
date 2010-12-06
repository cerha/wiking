# Copyright (C) 2006-2010 Brailcom, o.p.s.
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

import sys, re, os
import wiking, pytis
from wiking import debug, log, OPR

import mod_python, mod_python.util, mod_python.apache

class ModPythonFileUpload(wiking.FileUpload):
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


class ModPythonRequest(wiking.Request):
    """Mod_python server interface implementing the 'wiking.Request' interface."""
    
    def __init__(self, req):
        self._req = req
        # UTF-8 seems to always work, but it should probably be taken from request headers
        encoding = 'utf-8'
        # Store params and options in real dictionaries (not mod_python's mp_table).
        self._options = self._init_options()
        self._params = self._init_params(encoding)
        self._uri = unicode(req.uri, encoding)
        super(ModPythonRequest, self).__init__(encoding=encoding)

    def _init_options(self):
        options = self._req.get_options()
        return dict([(o, options[o]) for o in options.keys()])
        
    def _init_params(self, encoding):
        def init_value(value):
            if isinstance(value, (tuple, list)):
                return tuple([init_value(v) for v in value])
            elif isinstance(value, mod_python.util.Field):
                return ModPythonFileUpload(value, encoding)
            else:
                return unicode(value, encoding)
        fields = mod_python.util.FieldStorage(self._req)
        return dict([(k, init_value(fields[k])) for k in fields.keys()])

    def uri(self):
        return self._uri
    
    def unparsed_uri(self):
        self._req.unparsed_uri
        
    def param(self, name, default=None):
        return self._params.get(name, default)
        
    def params(self):
        return self._params.keys()
        
    def has_param(self, name):
        return self._params.has_key(name)
    
    def set_param(self, name, value):
        if value is None:
            if self._params.has_key(name):
                del self._params[name]
        else:
            self._params[name] = value
        
    def header(self, name, default=None):
        try:
            return self._req.headers_in[name]
        except KeyError:
            return default

    def set_header(self, name, value):
        self._req.headers_out.add(name, value)
        
    def port(self):
        return self._req.connection.local_addr[1]

    def https(self):
        return self._req.connection.local_addr[1] == wiking.cfg.https_port
    
    def remote_host(self):
        return self._req.get_remote_host()

    def server_hostname(self, current=False):
        if current:
            hostname = self._req.hostname
            # Should not be None by definition, but it happens.  We were not able to reproduce it,
            # but we have tracebacks, where server_hostname(True) returned None.
            if hostname:
                return self._req.hostname
        return self._req.server.server_hostname

    def set_status(self, status):
        self._req.status = status

    def send_http_header(self, content_type, lenght=None):
        self._req.content_type = content_type
        if lenght is not None:
            self._req.set_content_length(lenght)
        try:
            self._req.send_http_header()
        except IOError, e:
            raise wiking.ClosedConnection(str(e))

    def write(self, data):
        try:
            self._req.write(data)
        except IOError, e:
            raise wiking.ClosedConnection(str(e))
        
    def certificate(self):
        if self._req.ssl_var_lookup('SSL_CLIENT_VERIFY') == 'SUCCESS':
            certificate = self._req.ssl_var_lookup('SSL_CLIENT_CERT')
        else:
            certificate = None
        return certificate

    def option(self, name, default=None):
        return self._options.get(name, default)


class ModPythonHandler(object):
    """The Apache/mod_python handler interface.

    This class implements a mod_python specific wrapper.  The actual processing
    of requests is redirected to the 'wiking.Handler' instance, which does not
    depend on the web server environment.

    The instance of this class is created below to serve as mod_python entry
    point.  The instance is callable and will be called to serve the request.
    
    Mod_python instances are isolated by default, so Apache will create one
    instance of this class for each virtual host.  Moreover, there will be a
    separate set of mod_python instances for each web server instance.

    """
    def __init__(self):
        self._handler = None

    def _init(self, server_hostname, options, webmaster_address):
        # The initialization is postponed until the first request, since we need the information
        # from the request instance to initialize the configuration and the handler instance.
        def split(value):
            separator = value.find(':') != -1 and ':' or ','
            return tuple([d.strip() for d in value.split(separator)])
        cfg = wiking.cfg
        # Read the configuration file first, so that the Apache options have a higher priority.
        if options.has_key('config_file'):
            cfg.user_config_file = options.pop('config_file')
        for name, value in options.items():
            if name == 'translation_path':
                cfg.translation_path = tuple(cfg.translation_path) + split(value)
            elif name == 'resource_path':
                cfg.resource_path = split(value) + tuple(cfg.resource_path)
            elif name == 'modules':
                cfg.modules = split(value)
            elif name == 'database':
                cfg.dbname = value # For backwards compatibility...
            elif hasattr(cfg, name):
                option = cfg.option(name)
                if isinstance(option, cfg.StringOption):
                    setattr(cfg, name, value)
                elif isinstance(option, cfg.NumericOption):
                    if value.isdigit():
                        setattr(cfg, name, value)
                    else:
                        log(OPR, "Invalid numeric value for '%s':" % name, value)
                elif isinstance(option, cfg.BooleanOption):
                    if value.lower() in ('yes', 'no', 'true', 'false', 'on', 'off'):
                        setattr(cfg, name, value.lower() in ('yes', 'true', 'on'))
                    else:
                        log(OPR, "Invalid boolean value for '%s':" % name, value)
                else:
                    log(OPR, "Unable to set '%s' through Apache configuration. "
                        "PythonOption ignored." % name)
        domain = server_hostname
        if domain.startswith('www.'):
            domain = domain[4:]
        if cfg.webmaster_address is None:
            if webmaster_address is None or webmaster_address == '[no address given]':
                webmaster_address = 'webmaster@' + domain
            cfg.webmaster_address = webmaster_address
        if cfg.default_sender_address is None:
            cfg.default_sender_address = 'wiking@' + domain
        if cfg.dbname is None:
           cfg.dbname = server_hostname
        if cfg.resolver is None:
            cfg.resolver = wiking.WikingResolver()
        # Modify pytis configuration.
        import config
        config.dblisten = False
        config.log_exclude = [pytis.util.ACTION, pytis.util.EVENT, pytis.util.DEBUG]
        for option in ('dbname', 'dbhost', 'dbport', 'dbuser', 'dbpass', 'dbsslm', 'dbschemas',):
            setattr(config, option, getattr(cfg, option))
        config.dbconnections = cfg.connections
        config.dbconnection = config.option('dbconnection').default()
        del config
        self._handler = wiking.Handler(server_hostname)
        
    def __call__(self, request):
        if self._handler is None:
            opt = request.get_options()
            self._init(request.server.server_hostname,
                       dict([(o, opt[o]) for o in opt.keys()]),
                       request.server.server_admin)
        req = ModPythonRequest(request)
        if False: #not req.uri().startswith('/_'):
            import cProfile as profile, pstats, tempfile
            self._profile_req = req
            tmpfile = tempfile.NamedTemporaryFile().name
            profile.run('from wiking.mod_python_interface import handler as h; '
                        'h._profile_result = h._handler.handle(h._profile_req)',
                        tmpfile)
            try:
                stats = pstats.Stats(tmpfile)
                stats.strip_dirs()
                stats.sort_stats('cumulative')
                debug("Profile statistics for %s:" % req.uri())
                stats.stream = sys.stderr
                sys.stderr.write('   ')
                stats.print_stats()
                sys.stderr.flush()
            finally:
                os.remove(tmpfile)
            return self._profile_result
        else:
            return self._handler.handle(req)
            #result, t1, t2 = wiking.timeit(self._handler.handle, req)
            #log(OPR, "Request processed in %.1f ms (%.1f ms wall time):" % \
            #    (1000*t1, 1000*t2), req.uri())
            #return result

handler = ModPythonHandler()
"""The callable object expected to exist by mod_python (entry point)."""
