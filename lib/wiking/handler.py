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

class Handler(object):
    """Wiking handler.

    The main goal of the handler is to instantiate modules needed by the application and pass
    requests to these instances (module instances are cached on this level).  Results of request
    processing by modules is then handled by the handler again, including exception processing.

    """
    
    def __init__(self, hostname, options):
        dboptions = {'database': hostname}
        for name, value in options.items():
            if hasattr(cfg, name):
                setattr(cfg, name, value)
            else:
                dboptions[name] = value
        self._hostname = hostname
        self._dbconnection = pd.DBConnection(**dboptions)
        self._module_cache = {}
        # Initialize the system modules immediately.
        self._application = self._module('Application')
        self._exporter = cfg.exporter
        #log(OPR, 'New Handler instance for %s.' % hostname)

    def _module(self, name, **kwargs):
        key = (name, tuple(kwargs.items()))
        try:
            module = self._module_cache[key]
            #if module.__class__ is not cls:
            #    # Dispose the instance if the class definition has changed.
            #    raise KeyError()
        except KeyError:
            cls = get_module(name)
            args = (self._module,)
            if issubclass(cls, PytisModule):
                args += (cfg.resolver, self._dbconnection,)
            module = cls(*args, **kwargs)
            self._module_cache[key] = module
        return module

    def application(self):
        return self._application

    def handle(self, req):
        application = self._application
        try:
            req.path = req.path or ('index',)
            req.wmi = False # Will be set to True by `WikingManagementInterface'.
            modname = None
            try:
                application.configure(req)
                modname = application.resolve(req)
                module = self._module(modname)
                assert isinstance(module, RequestHandler)
                result = module.handle(req)
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
            node = result.build(req, modname,
                                application.menu(req),
                                application.panels(req, result.lang()),
                                application.stylesheets())
            output = translator(node.language()).translate(self._exporter.export(node))
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
        self._handler = None

    def __call__(self, request):
        if self._handler is None:
            opt = request.get_options()
            options = dict([(o, opt[o]) for o in opt.keys()])
            handler = self._handler = Handler(request.server.server_hostname, options)
        else:
            handler = self._handler
        req = WikingRequest(request, handler.application())
        if False:
            import profile, pstats, tempfile
            self._profile_req = req
            filename = tempfile.NamedTemporaryFile().name
            profile.run('from wiking.handler import handler as h; '
                        'h._profile_result = h._handler.handle(h._profile_req)',
                        filename)
            stats = pstats.Stats(filename)
            stats.sort_stats('cumulative')
            debug("Profile statistics for:", req.uri)
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
            return handler.handle(req)
        #result, t1, t2 = timeit(handler.handle, req)
        #log(OPR, "Request processed in %.1f ms (%.1f ms wall time):" % \
        #    (1000*t1, 1000*t2), req.uri)
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

