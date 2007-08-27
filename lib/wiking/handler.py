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
        self._mapping = self._module('Mapping')
        self._stylesheets = self._module('Stylesheets')
        self._languages = self._module('Languages')
        self._authentication = self._module('Authentication')
        self._config = self._module('Config')
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

    def handle(self, req):
        req.path = req.path or ('index',)
        req.set_auth_module(self._authentication)
        req.wmi = False # Will be set to True by `WikingManagementInterface'.
        module = None
        user = None
        try:
            try:
                self._config.configure(req)
                modname = self._mapping.resolve(req)
                module = self._module(modname)
                assert isinstance(module, RequestHandler)
                result = module.handle(req)
                if isinstance(result, int):
                    return result
                elif not isinstance(result, Document):
                    content_type, data = result
                    return req.result(data, content_type=content_type)
            # Always perform authentication at the end (if it was not
            # performed before) to handle authentication exceptions.
            except:
                user = req.user()
                raise
            else:
                user = req.user()
        except RequestError, e:
            if isinstance(e, HttpError):
                req.set_status(e.ERROR_CODE)
            lang = req.prefered_language(self._languages.languages(), raise_error=False)
            result = Document(e.title(), e.message(req), lang=lang)
        if module is None:
            module = self._mapping
        state = WikingNode.State(modname=module.name(),
                                 user=user,
                                 wmi=req.wmi,
                                 inline=req.param('display') == 'inline',
                                 show_panels=req.show_panels(),
                                 server_hostname=self._hostname)
        menu = module.menu(req)
        panels = module.panels(req, result.lang())
        styles = self._stylesheets.stylesheets()
        node = result.mknode('/'.join(req.path), state, menu, panels, styles)
        data = translator(node.language()).translate(self._exporter.export(node))
        return req.result(data)


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
        try:
            req = WikingRequest(request)
            if self._handler is None:
                self._handler = Handler(req.server_hostname(), req.options())
            return self._handler.handle(req)
        except Exception, e:
            handler = get_module('ErrorHandler')(None)
            return handler.handle_exception(req, e)

        #result, t1, t2 = timeit(self._handler.handle, req)
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

