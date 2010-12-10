# Copyright (C) 2006, 2007, 2008, 2009, 2010 Brailcom, o.p.s.
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
    _profiling_instance = None
    
    def __init__(self, server_hostname, webmaster_address, options):
        # Initialize the global configuration stored in 'wiking.cfg'.
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
            elif name == 'allow_profiling' and value:
                self.__class__._profiling_instance = self
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
        self._application = cfg.resolver.wiking_module('Application')
        self._exporter = cfg.exporter(translations=cfg.translation_path)

    def _serve_document(self, req, document):
        """Serve a document using the Wiking exporter."""
        node = document.build(req, self._application)
        context = self._exporter.context(node, node.lang(), sec_lang=node.sec_lang(), req=req)
        exported = self._exporter.export(context)
        req.result(context.translate(exported))

    def _serve_error_document(self, req, error):
        """Serve an error page using the Wiking exporter."""
        error.log(req)
        error.set_status(req)
        document = Document(error.title(req), error.message(req))
        self._serve_document(req, document)

    def _serve_minimal_error_document(self, req, error):
        """Serve a minimal error page using the minimalistic exporter."""
        error.log(req)
        error.set_status(req)
        node = lcg.ContentNode(req.uri().encode('utf-8'),
                               title=error.title(req),
                               content=error.message(req))
        exporter = MinimalExporter(translations=cfg.translation_path)
        try:
            lang = req.prefered_language()
        except:
            lang = cfg.default_language_by_domain.get(req.server_hostname(current=True),
                                                      cfg.default_language) or 'en'
        context = exporter.context(node, lang=lang)
        exported = exporter.export(context)
        req.result(context.translate(exported))

    def _handle(self, req):
        application = self._application
        try:
            try:
                result = application.handle(req)
                if isinstance(result, Document):
                    # Always perform authentication (if it was not performed before) to handle
                    # authentication exceptions here and prevent them in export time.
                    req.user()
                    self._serve_document(req, result)
                elif isinstance(result, (tuple, list)):
                    content_type, data = result
                    req.result(data, content_type=content_type)
                else:
                    # int is deprecated! Just for backwards compatibility.  
                    assert result is None or isinstance(result, int)
            except RequestError, error:
                try:
                    req.user()
                except RequestError:
                    # Ignore all errors within authentication except for AuthenticationError.
                    pass
                except AuthenticationError, auth_error:
                    self._serve_error_document(req, auth_error)
                self._serve_error_document(req, error)
            except (ClosedConnection, Done, Redirect):
                raise
            except Exception, e:
                # Try to return a nice error document produced by the exporter.
                try:
                    return application.handle_exception(req, e)
                except RequestError, error:
                    return self._serve_error_document(req, error)
        except ClosedConnection:
            pass
        except Done:
            pass
        except Redirect, r:
            req.redirect(r.uri(), args=r.args(), permanent=r.permanent())
        except Exception, e:
            # If error document export fails, return a minimal error page.  It is reasonable to
            # assume, that if RequestError handling fails, somethong is wrong with the exporter and
            # error document export will fail too, so it is ok, to have them handled both at the
            # same level above.
            try:
                application.handle_exception(req, e)
            except RequestError, error:
                self._serve_minimal_error_document(req, error)
            
    def handle(self, req):
        if self.__class__._profiling_instance: #and not req.uri().startswith('/_'):
            import cProfile as profile, pstats, tempfile
            self._profile_req = req
            tmpfile = tempfile.NamedTemporaryFile().name
            profile.run('from wiking.handler import Handler; '
                        'self = Handler._profiling_instance; '
                        'self._handle(self._profile_req)',
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
        else:
            #result, t1, t2 = timeit(self._handle, req)
            #log(OPR, "Request processed in %.1f ms (%.1f ms wall time):" % (1000*t1, 1000*t2), req.uri())
            self._handle(req)
            
try:
    # Only for backwards compatibility with older Apache/mod_python
    # configurations which relied on the entry point to be located in this
    # module (which is no longer specific to mod_python).  If
    # mod_python_interface faild to import, we are not running under
    # mod_python.
    import mod_python_interface
    handler = mod_python_interface.ModPythonHandler()
except:
    pass
