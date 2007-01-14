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

    There is just one instance of this class for the whole server.  This
    handler redirects the requests to 'SiteHandler' instances, which are
    specific to one site.  Multiple sites can be served this way.  One site is
    typically one virtual host (depending on Apache configuration).

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
        self._resolve_cache = {}
        self._module_cache = {}
        self._mapping = self._module('Mapping')
        self._panels = self._module('Panels')
        self._exporter = Exporter()
        #log(OPR, 'New SiteHandler instance for %s.' % dbconnection)

    def _module(self, name):
        try:
            module = self._module_cache[name]
        except KeyError:
            module = get_module(name)(self._dbconnection, self._resolver,
                                      self._module)
            self._module_cache[name] = module
        return module

    def _resolve(self, req, path):
        # return the target module and an object within this module (or a list
        # of objects) corresponding to the current request.
        identifier = path[0]
        try:
            modname = self._resolve_cache[identifier]
        except KeyError:
            modname = self._mapping.modname(identifier)
            self._resolve_cache[identifier] = modname
        module = self._module(modname)
        arg = module.resolve(req, path)
        return (module, arg)

    def _action(self, req, module, arg, **kwargs):
        action = req.param('action', arg and 'view' or 'list')
        if action.startswith('_') or not action.replace('_', '').isalpha():
            raise Exception("Invalid action.")
        method = getattr(module, action)
        if arg:
            kwargs['object'] = arg
        return method(req, **kwargs)

    def _stylesheets(self, req, panels):
        id = self._mapping.identifier('Stylesheets')
        if not id:
            return ()
        with_panels = req.show_panels() and panels
        return ['/'+id+'/'+stylesheet
                for stylesheet in self._module('Stylesheets').stylesheets()
                if with_panels or stylesheet != 'panels.css']

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
        path = [item for item in req.uri.split('/')[1:] if item]
        req.wmi = wmi = path and path[0] == '_wmi'
        doc = path and path[0] == '_doc'
        module = None
        try:
            #req.login(self._module('Users'))
            if doc:
                doc = req.param('display') != 'inline'
                result = self._doc(req, path[1:])
            elif wmi:
                if len(path) == 1:
                    path += ('Pages',)
                module = self._module(path[1])
                try:
                    arg = module.resolve(req)
                except NotFound:
                    msg = _("The requested object does not exist anymore!")
                    result = module.list(req, msg=msg)
                else:
                    result = self._action(req, module, arg)
            else:
                if not path:
                    path = ('index',)
                module, arg = self._resolve(req, path)
                result = self._action(req, module, arg)
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
            menu = wmi and self._module('Modules').menu(path[0]) or ()
            panels = ()
        else:
            menu = self._mapping.menu(result.lang())
            panels = self._panels.panels(result.lang())
            config.show_panels = req.show_panels()
        config.wmi = wmi
        config.doc = doc
        config.module = module
        config.user = req.user()
        node = result.mknode('/'.join(path), config, menu, panels, 
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


