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

    The instance is callable so it can be named 'handler' and it will work as
    a mod_python handler.

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
            import traceback
            message = ''.join(traceback.format_exception_only(*einfo[:2]))
            return req.error(message)

handler = Handler()


class SiteHandler(object):
    """Wiking site handler.

    There is one instance of this handler for each Wiking site.  See also the
    documentation of the 'Handler' class for more information about sites,
    virtualhosts and handlers.

    """

    def __init__(self, server, dbconnection, resolver):
        self._server = server
        self._dbconnection = dbconnection
        self._resolver = resolver
        self._module_cache = {}
        self._mapping = self._module('Mapping')
        self._panels = self._module('Panels')
        self._exporter = Exporter()
        #log(OPR, 'New SiteHandler instance for %s.' % dbconnection)

    def _module(self, name, identifier=None):
        try:
            module = self._module_cache[name]
            if identifier is not None and module.identifier() != identifier:
                raise KeyError(name) # Throw away...
        except KeyError:
            module = get_module(name)(self._dbconnection, self._resolver,
                                      self._module, identifier=identifier)
            self._module_cache[name] = module
        return module

    def _action(self, req, module, record):
        action = req.param('action', record and (req.wmi and 'show' or 'view')
                           or 'list')
        method = getattr(module, 'action_' + action)
        kwargs = record and dict(record=record) or {}
        return method(req, **kwargs)

    def _stylesheets(self, req, panels):
        with_panels = req.show_panels() and panels
        return [uri for uri in self._module('Stylesheets').stylesheets()
                if with_panels or not uri.endswith('panels.css')]

    def _doc(self, req, path):
        if path and path[0] == 'lcg':
            path = path[1:]
            basedir = lcg.config.doc_dir
        else:
            basedir = os.path.join(cfg.wiking_dir, 'doc', 'src')
        if not os.path.exists(basedir):
            raise Exception("Directory %s does not exist" % basedir)
        import glob, codecs
        # TODO: the documentation should be processed by LCG first into some
        # reasonable output format.
        for subdir in ('', 'user', 'admin'):
            basename = os.path.join(basedir, subdir, *path)
            variants = [f[-6:-4] for f in glob.glob(basename+'.*.txt')]
            if variants:
                break
        else:
            raise NotFound()
        lang = req.prefered_language(variants)
        filename = '.'.join((basename, lang, 'txt'))
        f = codecs.open(filename, encoding='utf-8')
        text = "".join(f.readlines())
        f.close()
        content = lcg.Parser().parse(text)
        if len(content) == 1 and isinstance(content[0], lcg.Section):
            title = content[0].title()
            content = lcg.SectionContainer(content[0].content(), toc_depth=0)
        else:
            title = ' :: '.join(path)
        return Document(title, content, lang=lang, variants=variants)

    def handle(self, req):
        req.wmi = wmi = req.path and req.path[0] == '_wmi'
        doc = req.path and req.path[0] == '_doc'
        module = None
        try:
            #req.login(self._module('Users'))
            if doc:
                doc = req.param('display') != 'inline'
                result = self._doc(req, req.path[1:])
            else:
                if wmi:
                    if len(req.path) == 1:
                        req.path += ('Pages',)
                    modname = req.path[1]
                else:
                    req.path = req.path or ('index',)
                    modname = self._mapping.modname(req.path[0])
                module = self._module(modname)
                record = module.resolve(req)
                result = self._action(req, module, record)
            if not isinstance(result, Document):
                content_type, data = result
                return req.result(data, content_type=content_type)
        except HttpError, e:
            req.set_status(e.ERROR_CODE)
            lang = req.prefered_language(self._module('Languages').languages(),
                                         raise_error=False)
            if isinstance(e, Unauthorized):
                content = LoginDialog(req)
                if e.args:
                    content = (ErrorMessage(e.args[0]), content)
            else:
                content = lcg.TextContent(e.msg(req))
            result = Document(e.title(), content, lang=lang)
        config = self._module('Config').config(self._server, result.lang())
        if wmi or doc:
            config.site_title = wmi and \
                                _("Wiking Management Interface") or \
                                _("Wiking Help System")
            config.site_subtitle = None
            menu = wmi and self._module('Modules').menu(req.path[0]) or ()
            panels = ()
        else:
            menu = self._mapping.menu(result.lang())
            panels = self._panels.panels(result.lang())
            config.show_panels = req.show_panels()
        config.wmi = wmi
        config.doc = doc
        config.module = module
        config.user = req.user()
        node = result.mknode('/'.join(req.path), config, menu, panels, 
                             self._stylesheets(req, panels))
        data = translator(node.language()).translate(self._exporter.page(node))
        return req.result(data)


# def authenhandler(req):
#      pw = req.get_basic_auth_pw()
#      user = req.user
#      u = authStore.fetch_object(session, user)
#      if (u and u.password == crypt.crypt(pw, pw[:2])):
#          return apache.OK
#      else:
#          return apache.HTTP_UNAUTHORIZED


