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

_ = lcg.TranslatableTextFactory('wiking')

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

    def _serve_error_document(self, req, error):
        if isinstance(error, HttpError):
            req.set_status(error.ERROR_CODE)
        document = Document(error.title(), error.message(req))
        return self._serve_document(req, document)

    def _serve_document(self, req, document):
        node = document.build(req, self._application)
        context = self._exporter.context(node, node.lang(), req=req)
        exported = self._exporter.export(context)
        return req.result(context.translate(exported))

    def handle(self, req):
        application = self._application
        req.path = req.path or ('index',)
        try:
            try:
                application.configure(req)
                result = application.handle(req)
                if isinstance(result, Document):
                    # Always perform authentication (if it was not performed before) to handle
                    # authentication exceptions here and prevent them in export time.
                    req.user()
                    return self._serve_document(req, result)
                elif isinstance(result, int):
                    return result
                else:
                    content_type, data = result
                    return req.result(data, content_type=content_type)
            except RequestError, e:
                try:
                    req.user()
                except AuthenticationError, ae:
                    return self._serve_error_document(req, ae)
                return self._serve_error_document(req, e)
            except ClosedConnection:
                return req.done()
            except Exception, e:
                # Try to return a nice error document produced by the exporter.
                try:
                    return application.handle_exception(req, e)
                except InternalServerError, ie:
                    return self._serve_error_document(req, ie)
        except ClosedConnection:
            return req.done()
        except Exception, e:
            # If error document export fails, return an ugly error message.  It is reasonable to
            # assume, that if RequestError handling fails, somethong is wrong with the exporter and
            # nice error document export will fail too, so it is ok, to have them handled both at
            # the same level above.
            try:
                return application.handle_exception(req, e)
            except InternalServerError, error:
                req.set_status(error.ERROR_CODE)

                admin = cfg.webmaster_address
                from xml.sax.saxutils import escape
                from wiking import __version__
                texts = (
                    error.ERROR_CODE, error.title(),
                    error.title(),
                    _("The server was unable to complete your request."),
                    _("Please inform the server administrator, %(admin)s if the problem persists.",
                      admin=cfg.webmaster_address),
                    _("The error message was:"),
                    escape(error.args[0]),
                    __version__)
                try:
                    tr = translator(req.prefered_language())
                    texts = tuple([tr.translate(t) for t in texts])
                except:
                    pass
                result = (
                    '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN">\n' 
                    '<html>\n'
                    '<head>\n'
                    ' <title>%d %s</title>\n'
                    ' <link rel="stylesheet" type="text/css" href="/_css/default.css" />\n'
                    '</head>\n'
                    '<body>\n'
                    ' <div id="main-menu"></div>\n'
                    ' <div id="content">\n'
                    '  <h1>%s</h1>\n'
                    '  <p>%s</p>\n'
                    '  <p>%s</p>\n'
                    '  <p>%s</p>\n'
                    '  <pre class="lcg-preformatted-text">%s</pre>\n'
                    ' </div>\n'
                    ' <div id="wiking-bar">\n'
                    '  <hr/>\n'
                    '  <span><a href="http://www.freebsoft.org/wiking">Wiking</a> %s</span>\n'
                    ' </div>\n'
                    '</body>\n'
                    '</html>\n') 
                return req.result(result % texts)


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

    def _init(self, hostname, options, webmaster_address):
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
        domain = hostname
        if domain.startswith('www.'):
            domain = domain[4:]
        if cfg.webmaster_address is None:
            if webmaster_address is None or webmaster_address == '[no address given]':
                webmaster_address = 'webmaster@' + domain
            cfg.webmaster_address = webmaster_address
        if cfg.default_sender_address is None:
            cfg.default_sender_address = 'wiking@' + domain
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
            self._init(request.server.server_hostname,
                       dict([(o, opt[o]) for o in opt.keys()]),
                       request.server.server_admin)
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

