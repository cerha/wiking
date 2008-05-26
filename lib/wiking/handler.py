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

class Handler(object):
    """Wiking handler.

    The handler passes the actual request processing to the current application.  Its main job is
    handling errors during this processing and dealing with its result (typically exporting the
    document into HTML and sending it to the client).

    """
    def __init__(self, hostname):
        self._hostname = hostname
        self._application = cfg.resolver.wiking_module('Application')
        self._exporter = cfg.exporter(translations=cfg.translation_path)
        #log(OPR, 'New Handler instance for %s.' % hostname)

    def handle(self, req):
        application = self._application
        try:
            req.path = req.path or ('index',)
            try:
                application.configure(req)
                result = application.handle(req)
                if not isinstance(result, Document):
                    if isinstance(result, int):
                        return result
                    else:
                        content_type, data = result
                        return req.result(data, content_type=content_type)
                # Always perform authentication at the end (if it was not performed before) to
                # handle authentication exceptions here and prevent them in export time.
                req.user()
            except RequestError, e:
                try:
                    req.user()
                except AuthenticationError, ae:
                    result = Document(ae.title(), ae.message(req))
                else:
                    if isinstance(e, HttpError):
                        req.set_status(e.ERROR_CODE)
                    result = Document(e.title(), e.message(req))
            node = result.build(req, application)
            context = self._exporter.context(node, node.lang(), req=req)
            output = context.translate(self._exporter.export(context))
            return req.result(output)
        except Exception, e:
            return application.handle_exception(req, e)


class ModPythonHandler(object):
    """The main Apache/mod_python handler interface.

    This class implements a mod_python specific wrapper.  The actual processing of requests is
    redirected to the 'Handler' instance, which does not depend on the web server environment.
    
    Mod_python instances are isolated by default, so Apache will create one instance of this class
    for each virtual host.  Moreover, there will be a separate set of mod_python instances for each
    web server instance.

    """
    def __init__(self):
        self._application = None
        self._handler = None
        self._initialized = False

    def _init(self, hostname, options):
        # The initialization is postponed until the first request, since we need the information
        # from the request instance to initialize the configuration and the handler instance.
        def split(value):
            separator = value.find(':') != -1 and ':' or ','
            return tuple([d.strip() for d in value.split(separator)])
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
        if cfg.resolver is None:
            dbconnection = pd.DBConnection(database=cfg.dbname or hostname,
                                           user=cfg.dbuser, host=cfg.dbhost, port=cfg.dbport)
            cfg.resolver = WikingResolver(dbconnection, cfg.modules, cfg.maintenance)
        self._application = cfg.resolver.wiking_module('Application')
        self._handler = Handler(hostname)
        self._initialized = True
        
    def __call__(self, request):
        if not self._initialized:
            opt = request.get_options()
            self._init(request.server.server_hostname, dict([(o, opt[o]) for o in opt.keys()]))
        req = WikingRequest(request, self._application)
        if False:
            import profile, pstats, tempfile
            self._profile_req = req
            filename = tempfile.NamedTemporaryFile().name
            profile.run('from wiking.handler import handler as h; '
                        'h._profile_result = h._handler.handle(h._profile_req)',
                        filename)
            stats = pstats.Stats(filename)
            stats.sort_stats('cumulative')
            debug("Profile statistics for:", req.uri())
            stdout = sys.stdout
            sys.stdout = sys.stderr
            try:
                stats.print_stats()
            finally:
                sys.stdout = stdout
                os.remove(filename)
            sys.stderr.flush()
            return self._profile_result
        else:
            return self._handler.handle(req)
        #result, t1, t2 = timeit(self._handler.handle, req)
        #log(OPR, "Request processed in %.1f ms (%.1f ms wall time):" % \
        #    (1000*t1, 1000*t2), req.uri())
        #return result

handler = ModPythonHandler()
"""The instance is callable so this makes it work as a mod_python handler."""

# def authenhandler(req):
#      pw = req.get_basic_auth_pw()
#      user = req.user
#      u = authStore.fetch_object(session, user)
#      if (u and u.password == crypt.crypt(pw, pw[:2])):
#          return apache.OK
#      else:
#          return apache.HTTP_UNAUTHORIZED

