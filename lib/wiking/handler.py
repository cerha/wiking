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

_ = lcg.TranslatableTextFactory('wiking')

class Handler(object):
    """The main Apache/mod_python handler interface.

    There is just one instance of this class for the whole server.  Well, more
    precisely, there is one instance of the handler per each web server
    instance -- Apache typically runs several independent instances
    concurrently.  Anyway, this handler redirects the requests within one
    webserver instance to 'SiteHandler' instances, which are specific to one
    site.  Multiple sites can be served this way.  One site is typically one
    virtual host (depending on web server configuration).

    """
    def __init__(self):
        self._site_handlers = {}

    def _site_handler(self, server, dbconnection):
        key = hash(dbconnection)
        try:
            site_handler = self._site_handlers[key]
        except KeyError:
            resolver = WikingResolver()
            site_handler = SiteHandler(server, dbconnection, resolver)
            self._site_handlers[key] = site_handler
        return site_handler
    
    def __call__(self, request):
        req = WikingRequest(request)
        dbconnection = pd.DBConnection(**req.options)
        try:
            site_handler = self._site_handler(req.server, dbconnection)
            #result, t1, t2 = timeit(site_handler.handle, req)
            #log(OPR, "Request processed in %.1f ms (%.1f ms wall time):" % \
            #    (1000*t1, 1000*t2), req.uri)
            return site_handler.handle(req)
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


handler = Handler()
"""The instance is callable so this makes it work as a mod_python handler."""


class SiteHandler(object):
    """Wiking site handler.

    There is one instance of this handler for each Wiking site.  See also the
    documentation of the 'Handler' class for more information about sites,
    virtualhosts and handlers.

    The main goal of the site handler is to instantiate the modules needed by
    the application and pass the requests to the instances of the modules.
    Module instances are cached on this level.

    The other responsibility is to process the result of the module request
    handler and handle 'RequestError' exceptions, such as 'NotFound',
    'NotAccaeptable', etc, since these errors should be presented with all the
    site navigation, panels etc.

    """

    def __init__(self, server, dbconnection, resolver):
        self._server = server
        self._dbconnection = dbconnection
        self._resolver = resolver
        self._module_cache = {}
        # Initialize the system modules immediately.
        self._mapping = self._module('Mapping')
        self._stylesheets = self._module('Stylesheets')
        self._languages = self._module('Languages')
        self._config = self._module('Config')
        self._users = self._module('Users')
        self._exporter = Exporter() #self._config.exporter or Exporter()
        #log(OPR, 'New SiteHandler instance for %s.' % dbconnection)

    def _module(self, name):
        cls = get_module(name)
        try:
            module = self._module_cache[name]
            if module.__class__ is not cls:
                # Dispose the instance if the class definition has changed.
                raise KeyError()
        except KeyError:
            args = (self._module, self._resolver)
            if issubclass(cls, PytisModule):
                args += (self._dbconnection,)
            module = cls(*args)
            self._module_cache[name] = module
        return module

    def handle(self, req):
        req.path = req.path or ('index',)
        req.wmi = False # Will be set to True by `WikingManagementInterface'.
        module = None
        user = None
        try:
            try:
                req.login(self._users)
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
            lang = req.prefered_language(self._languages.languages(),
                                         raise_error=False)
            result = Document(e.title(), e.message(req), lang=lang)
        if module is None:
            module = self._mapping
        config = self._config.config(self._server, result.lang())
        config.modname = module.name()
        config.user = user
        config.wmi = req.wmi
        config.inline = req.param('display') == 'inline'
        config.show_panels = req.show_panels()
        menu = module.menu(req, result.lang())
        panels = module.panels(req, result.lang())
        styles = [s for s in self._stylesheets.stylesheets()
                  if s.file() != 'panels.css' or config.show_panels and panels]
        node = result.mknode('/'.join(req.path), config, menu, panels, styles)
        exporter = config.exporter or self._exporter
        data = translator(node.language()).translate(exporter.export(node))
        return req.result(data)


# def authenhandler(req):
#      pw = req.get_basic_auth_pw()
#      user = req.user
#      u = authStore.fetch_object(session, user)
#      if (u and u.password == crypt.crypt(pw, pw[:2])):
#          return apache.OK
#      else:
#          return apache.HTTP_UNAUTHORIZED

