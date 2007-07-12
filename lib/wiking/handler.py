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

    The main goal of the handler is to instantiate modules needed by the application and pass the
    requests to these instances.  Module instances are cached on this level.

    The other responsibility is to process the result of the module request handler and handle
    'RequestError' exceptions.

    """

    def __init__(self, server, dbconnection):
        self._server = server
        self._dbconnection = dbconnection
        self._module_cache = {}
        self._resolver = WikingResolver()
        # Initialize the system modules immediately.
        self._mapping = self._module('Mapping')
        self._stylesheets = self._module('Stylesheets')
        self._authentication = self._module('Authentication')
        self._config = self._module('Config')
        config = self._config.config()
        self._exporter = config.exporter or Exporter()
        if config.resolver is not None:
            self._resolver = config.resolver
        #log(OPR, 'New Handler instance for %s.' % server.server_hostname)

    def _module(self, name, **kwargs):
        cls = get_module(name)
        key = (name, tuple(kwargs.items()))
        try:
            module = self._module_cache[key]
            if module.__class__ is not cls:
                # Dispose the instance if the class definition has changed.
                raise KeyError()
        except KeyError:
            args = (self._module, self._resolver)
            if issubclass(cls, PytisModule):
                args += (self._dbconnection,)
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
                modname = self._mapping.resolve(req)
                module = self._module(modname)
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
            lang = req.prefered_language(self._module('Languages').languages(), raise_error=False)
            result = Document(e.title(), e.message(req), lang=lang)
        if module is None:
            module = self._mapping
        config = self._config.config()
        config.modname = module.name()
        config.user = user
        config.wmi = req.wmi
        config.inline = req.param('display') == 'inline'
        config.show_panels = req.show_panels()
        config.server_hostname = self._server.server_hostname
        menu = module.menu(req)
        panels = module.panels(req, result.lang())
        styles = self._stylesheets.stylesheets()
        node = result.mknode('/'.join(req.path), config, menu, panels, styles)
        exporter = self._exporter
        data = translator(node.language()).translate(exporter.export(node))
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
        req = WikingRequest(request)
        dbconnection = pd.DBConnection(**req.options)
        try:
            if self._handler is None:
                self._handler = Handler(req.server, dbconnection)
            #result, t1, t2 = timeit(self._handler.handle, req)
            #log(OPR, "Request processed in %.1f ms (%.1f ms wall time):" % \
            #    (1000*t1, 1000*t2), req.uri)
            return self._handler.handle(req)
        except Exception, e:
            if isinstance(e, pd.DBException):
                try:
                    if e.exception() and e.exception().args:
                        errstr = e.exception().args[0]
                    else:
                        errstr = e.message()
                    result = maybe_install(req, dbconnection, errstr)
                    if result is not None:
                        return req.result(result)
                except:
                    pass
            einfo = sys.exc_info()
	    info = (("URI", req.uri),
                    ("Remote host", req.get_remote_host()),
                    ("HTTP referrer", req.header('Referer')),
                    ("User agent", req.header('User-Agent')),
                    )
            import traceback
            text = "\n".join(["%s: %s" % pair for pair in info]) + \
                   "\n\n" + "".join(traceback.format_exception(*einfo))
            try:
                if cfg.bug_report_address is not None:
                    send_mail('wiking@' + req.server.server_hostname,
                              cfg.bug_report_address,
                              'Wiking Error: ' + req.server.server_hostname,
                              text + "\n\n" + cgitb.text(einfo),
                              "<html><pre>"+ text +"</pre>"+ \
                              cgitb.html(einfo) +"</html>",
                              smtp_server=cfg.smtp_server)
                    log(OPR, "Traceback sent to:", cfg.bug_report_address)
                else:
                    log(OPR, "Error:", cgitb.text(einfo))
            except Exception, e:
                log(OPR, "Error in exception handling:", e)
                log(OPR, "The original exception was:", text)
            import traceback
            message = ''.join(traceback.format_exception_only(*einfo[:2]))
            return req.error(message)


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

