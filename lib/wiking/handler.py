# Copyright (C) 2006, 2007, 2008, 2009 Brailcom, o.p.s.
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

import pytis.data
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

    def _serve_document(self, req, document):
        """Serve a document using the Wiking exporter."""
        node = document.build(req, self._application)
        context = self._exporter.context(node, node.lang(), sec_lang=node.sec_lang(), req=req)
        exported = self._exporter.export(context)
        return req.result(context.translate(exported))

    def _serve_error_document(self, req, error):
        """Serve an error page using the Wiking exporter."""
        if isinstance(error, HttpError):
            req.set_status(error.ERROR_CODE)
        document = Document(error.title(), error.message(req))
        return self._serve_document(req, document)

    def _serve_minimal_error_document(self, req, error):
        """Serve a minimal error page using the minimalistic exporter."""
        if isinstance(error, HttpError):
            req.set_status(error.ERROR_CODE)
        node = lcg.ContentNode(req.uri().encode('utf-8'),
                               title=error.title(),
                               content=error.message(req))
        exporter = MinimalExporter(translations=cfg.translation_path)
        try:
            lang = req.prefered_language()
        except:
            lang = cfg.default_language_by_domain.get(req.server_hostname(current=True),
                                                      cfg.default_language) or 'en'
        context = exporter.context(node, lang=lang)
        exported = exporter.export(context)
        return req.result(context.translate(exported))

    def handle(self, req):
        application = self._application
        try:
            try:
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
            except RequestError, error:
                try:
                    req.user()
                except (AuthenticationError, Abort), auth_error:
                    return self._serve_error_document(req, auth_error)
                return self._serve_error_document(req, error)
            except ClosedConnection:
                return req.done()
            except Exception, e:
                # Try to return a nice error document produced by the exporter.
                try:
                    return application.handle_exception(req, e)
                except RequestError, error:
                    return self._serve_error_document(req, error)
        except ClosedConnection:
            return req.done()
        except Exception, e:
            # If error document export fails, return a minimal error page.  It is reasonable to
            # assume, that if RequestError handling fails, somethong is wrong with the exporter and
            # error document export will fail too, so it is ok, to have them handled both at the
            # same level above.
            try:
                return application.handle_exception(req, e)
            except RequestError, error:
                return self._serve_minimal_error_document(req, error)


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
        if cfg.dbname is None:
           cfg.dbname = hostname
        if cfg.resolver is None:
            cfg.resolver = WikingResolver()
        # Modify pytis configuration.
        import config
        config.dblisten = False
        config.log_exclude = [pytis.util.ACTION, pytis.util.EVENT, pytis.util.DEBUG]
        for option in ('dbname', 'dbhost', 'dbport', 'dbuser', 'dbpass', 'dbsslm'):
            setattr(config, option, getattr(cfg, option))
        config.dbconnections = cfg.connections
        config.dbconnection = config.option('dbconnection').default()
        del config
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
            import cProfile as profile, pstats, tempfile
            self._profile_req = req
            tmpfile = tempfile.NamedTemporaryFile().name
            profile.run('from wiking.handler import handler as h; '
                        'h._profile_result = h._handler.handle(h._profile_req)',
                        tmpfile)
            try:
                stats = pstats.Stats(tmpfile)
                stats.strip_dirs()
                stats.sort_stats('cumulative')
                debug("Profile statistics for %s:" % req.uri())
                stats.stream = sys.stderr
                stats.print_stats()
                sys.stderr.flush()
            finally:
                os.remove(tmpfile)
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

