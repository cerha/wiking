# Copyright (C) 2006, 2007, 2008, 2009, 2010, 2011, 2012, 2013 Brailcom, o.p.s.
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

import os
import sys

import wiking
import lcg
from pytis.util import OPERATIONAL, log

_ = lcg.TranslatableTextFactory('wiking')


class Handler(object):
    """Wiking handler.

    The handler passes the actual request processing to the current application.  Its main job is
    handling errors during this processing and dealing with its result (typically exporting the
    document into HTML and sending it to the client).

    """
    _instance = None # Used for profiling only.
    
    def __init__(self, req):
        """Initialize the global wiking handler instance.
        
        The argument 'req' is the initial request which triggered the Handler
        creation, however the handler will normally exist much longer thant for
        this single request and its method 'handle()' will be called to handle
        also other requests (including this one).  The constructor only needs
        the request instance to gather some global information to be able to
        initialize the configuration etc.
        
        """
        # Initialize the global configuration stored in 'wiking.cfg'.
        config_file = req.option('config_file')
        if config_file:
            # Read the configuration file first, so that the request options have a higher priority.
            wiking.cfg.user_config_file = config_file
        for option in wiking.cfg.options():
            name = option.name()
            value = req.option(name)
            if value and name != 'config_file':
                if name in ('translation_path', 'resource_path', 'modules'):
                    separator = value.find(':') != -1 and ':' or ','
                    value = tuple([d.strip() for d in value.split(separator)])
                    if name == 'translation_path':
                        value = tuple(wiking.cfg.translation_path) + value
                    elif name == 'resource_path':
                        value += tuple(wiking.cfg.resource_path)
                elif isinstance(option, wiking.cfg.NumericOption):
                    if value.isdigit():
                        value = int(value)
                    else:
                        log(OPERATIONAL, "Invalid numeric value for '%s':" % name, value)
                        continue
                elif isinstance(option, wiking.cfg.BooleanOption):
                    if value.lower() in ('yes', 'true', 'on'):
                        value = True
                    elif value.lower() in ('no', 'false', 'off'):
                        value = False
                    else:
                        log(OPERATIONAL, "Invalid boolean value for '%s':" % name, value)
                        continue
                elif not isinstance(option, wiking.cfg.StringOption):
                    log(OPERATIONAL, "Unable to set '%s' through request options." % name)
                    continue
                setattr(wiking.cfg, name, value)
        # Apply default values which depend on the request.
        server_hostname = wiking.cfg.server_hostname
        if server_hostname is None:
            # TODO: The name returned by req.server_hostname() works for simple
            # cases where there are no server aliases, but we can not guarantee
            # that it is really unique.  Thus might be safer to raise an error
            # when req.primary_server_hostname() returns None and require
            # configuring server_hostname explicitly.
            server_hostname = req.primary_server_hostname() or req.server_hostname()
            wiking.cfg.server_hostname = server_hostname
        domain = server_hostname
        if domain.startswith('www.'):
            domain = domain[4:]
        if wiking.cfg.webmaster_address is None:
            wiking.cfg.webmaster_address = 'webmaster@' + domain
        if wiking.cfg.default_sender_address is None:
            wiking.cfg.default_sender_address = 'wiking@' + domain
        if wiking.cfg.dbname is None:
            wiking.cfg.dbname = server_hostname
        if wiking.cfg.resolver is None:
            wiking.cfg.resolver = wiking.WikingResolver(wiking.cfg.modules)
        # Modify pytis configuration.
        import pytis.util
        import config
        config.dblisten = False
        config.log_exclude = [pytis.util.ACTION, pytis.util.EVENT, pytis.util.DEBUG]
        for option in ('dbname', 'dbhost', 'dbport', 'dbuser', 'dbpass', 'dbsslm', 'dbschemas',):
            setattr(config, option, getattr(wiking.cfg, option))
        config.dbconnections = wiking.cfg.connections
        config.dbconnection = config.option('dbconnection').default()
        config.resolver = wiking.cfg.resolver
        del config
        self._application = application = wiking.module.Application
        self._exporter = wiking.cfg.exporter(translations=wiking.cfg.translation_path)
        application.initialize(config_file)
        # Save the current handler instance for profiling purposes.
        Handler._instance = self

    def _resource_provider(self, req):
        styles = []
        for x in self._application.stylesheets(req):
            if isinstance(x, basestring):
                x = lcg.Stylesheet(x, uri=x)
            styles.append(x)
        return lcg.ResourceProvider(resources=styles, dirs=wiking.cfg.resource_path)

    def _build(self, req, document):
        """Return the 'WikingNode' instance representing the given document.

        The whole application menu structure must be built in order to create
        the 'WikingNone' instance ('WikingNode' is derived from
        'lcg.ContentNode').
        
        """
        application = self._application
        uri = '/' + req.uri().strip('/')
        lang = document.lang() or req.preferred_language(raise_error=False) or 'en'
        nodes = {}
        resource_provider = self._resource_provider(req)
        def mknode(item):
            # Caution - make the same uri transformation as above to get same
            # results in all cases (such as for '/').
            item_uri = '/' + item.id().strip('/')
            if item_uri == uri:
                heading = document.title() or item.title()
                if heading and document.subtitle():
                    heading = lcg.concat(heading, ' :: ', document.subtitle())
                content = document.content()
                if isinstance(content, (list, tuple)):
                    content = lcg.Container([c for c in content if c is not None])
                panels = application.panels(req, lang)
                variants = document.variants()
                if variants is None:
                    variants = item.variants()
            else:
                heading = item.title()
                content = lcg.Content()
                panels = ()
                variants = item.variants()
            hidden = item.hidden()
            if variants is None:
                variants = application.languages()
            elif lang not in variants:
                hidden = True
            # The identifier is encoded to allow unicode characters within it.  The encoding
            # actually doesnt't matter, we just need any unique 8-bit string.
            node = wiking.WikingNode(item_uri.encode('utf-8'), title=item.title(),
                                     page_heading=heading,
                                     descr=item.descr(), content=content,
                                     lang=lang, sec_lang=document.sec_lang(),
                                     variants=variants or (),
                                     active=item.active(), foldable=item.foldable(), hidden=hidden,
                                     children=[mknode(i) for i in item.submenu()],
                                     resource_provider=resource_provider,
                                     globals=document.globals(),
                                     panels=panels, layout=document.layout())
            nodes[item_uri] = node
            return node
        top_level_nodes = [mknode(item) for item in application.menu(req)]
        # Find the parent node by the identifier prefix.
        parent = None
        for i in range(len(req.path) - 1):
            key = '/' + '/'.join(req.path[:len(req.path) - i - 1])
            if key in nodes:
                parent = nodes[key]
                break
        try:
            node = nodes[uri]
        except KeyError:
            # Create the current document's node if it was not created with the menu.
            variants = document.variants() or parent and parent.variants() or None
            node = mknode(wiking.MenuItem(uri, document.title(), hidden=True, variants=variants))
            if parent:
                parent.add_child(node)
            else:
                top_level_nodes.append(node)
        wiking.WikingNode('__wiking_root_node__', title='root', content=lcg.Content(),
                          children=top_level_nodes)
        return node

    def _serve_document(self, req, document, status_code=200):
        """Serve a document using the Wiking exporter."""
        node = self._build(req, document)
        context = self._exporter.context(node, node.lang(), sec_lang=node.sec_lang(), req=req)
        exported = self._exporter.export(context)
        #exported, t1, t2 = timeit(self._exporter.export, context)
        #log(OPERATIONAL, "Document exported in %.1f ms (%.1f ms CPU):" %
        #                  (1000*t2, 1000*t1), req.uri())
        return req.send_response(context.localize(exported), status_code=status_code)

    def _serve_content(self, req, content):
        """Serve a document using the Wiking exporter."""
        node = lcg.ContentNode(req.uri(), content=content,
                               resource_provider=self._resource_provider(req))
        context = self._exporter.context(node, lang=req.preferred_language(), req=req)
        return req.send_response(context.localize(content.export(context)))

    def _handle_maintenance_mode(self, req):
        import httplib
        # Translators: Meaning that the system (webpage) does not work now
        # because we are updating/fixing something but will work again after
        # the maintaince is finished.
        node = lcg.ContentNode(req.uri().encode('utf-8'), title=_("Maintenance Mode"),
                               content=lcg.p(_("The system is temporarily down for maintenance.")))
        exporter = wiking.MinimalExporter(translations=wiking.cfg.translation_path)
        try:
            lang = req.preferred_language()
        except:
            lang = wiking.cfg.default_language_by_domain.get(req.server_hostname(),
                                                             wiking.cfg.default_language) or 'en'
        context = exporter.context(node, lang=lang)
        exported = exporter.export(context)
        return req.send_response(context.localize(exported),
                                 status_code=httplib.SERVICE_UNAVAILABLE)

    def _handle_request_error(self, req, error):
        if not isinstance(error, (wiking.AuthenticationError,
                                  wiking.Abort, wiking.DisplayDocument)):
            self._application.log_error(req, error)
        document = wiking.Document(error.title(req), error.content(req))
        return self._serve_document(req, document, status_code=error.status_code(req))

    def _handle(self, req):
        try:
            try:
                if wiking.cfg.maintenance and not req.uri().startswith('/_resources/'):
                    # TODO: excluding /_resources/ is here to make stylesheets
                    # available for the maintenance error page.  The URI is
                    # however not necassarily correct (application may change
                    # it).  Better would most likely be including some basic styles
                    # directly in MinimalExporter.
                    return self._handle_maintenance_mode(req)
                result = self._application.handle(req)
                if isinstance(result, (tuple, list)):
                    # Temporary backwards compatibility conversion.
                    content_type, data = result
                    result = wiking.Response(data, content_type=content_type)
                if isinstance(result, (lcg.Content, wiking.Document)):
                    # Always perform authentication (if it was not performed before) to handle
                    # authentication exceptions here and prevent them in export time.
                    req.user()
                    if isinstance(result, wiking.Document):
                        return self._serve_document(req, result)
                    else:
                        return self._serve_content(req, result)
                elif isinstance(result, wiking.Response):
                    last_modified = result.last_modified()
                    if last_modified is not None and req.cached_since(last_modified):
                        raise wiking.NotModified()
                    for header, value in result.headers():
                        req.set_header(header, value)
                    filename = result.filename()
                    if filename:
                        req.set_header('Content-Disposition',
                                       'attachment; filename="%s"' % filename)
                    return req.send_response(result.data(), content_type=result.content_type(),
                                             content_length=result.content_length(),
                                             status_code=result.status_code(),
                                             last_modified=result.last_modified())
                else:
                    raise Exception('Invalid wiking handler result: %s' % type(result))
            except wiking.NotModified as error:
                return req.send_response('', status_code=error.status_code(req), content_type=None)
            except wiking.RequestError as error:
                # Try to authenticate now, but ignore all errors within authentication except
                # for AuthenticationError.
                try:
                    req.user()
                except wiking.RequestError:
                    pass
                except wiking.AuthenticationError as auth_error:
                    error = auth_error
                return self._handle_request_error(req, error)
            except wiking.DisplayDocument as e:
                return self._serve_document(req, e.document())
            except wiking.ClosedConnection:
                return []
            except wiking.Redirect as r:
                return req.redirect(r.uri(), args=r.args(), permanent=r.permanent())
        except Exception:
            # Any other unhandled exception is an Internal Server Error.  It is
            # handled in a separate try/except block to chatch also errors in
            # except blocks of the inner level.
            einfo = sys.exc_info()
            self._application.send_bug_report(req, einfo)
            if not wiking.cfg.debug:
                # When debug is on, the full traceback goes to the browser
                # window and it is better to leave the error log for printing
                # debugging information (the exception makes too much noise
                # there...) so we log the traceback only when debug is off.
                self._application.log_traceback(req, einfo)
            return self._handle_request_error(req, wiking.InternalServerError(einfo))
            
    def handle(self, req):
        if not hasattr(self, '_first_request_served'):
            if __debug__:
                wiking.debug("Python optimization off.")
            else:
                wiking.debug("Python optimization on.")
        if wiking.cfg.debug and (wiking.cfg.profile or req.param('profile') == '1'):
            enable_profiling = True
            if not hasattr(self, '_first_request_served'):
                if req.param('ignore_first'):
                    wiking.debug("Profiling disabled for the initial request.")
                    enable_profiling = False
                else:
                    wiking.debug("Profiling note: This is an initial request.")
        else:
            enable_profiling = False
        self._first_request_served = True
        if enable_profiling:
            import cProfile as profile
            import pstats
            import tempfile
            self._profile_req = req
            queries = []
            def query_callback(query, start_time, end_time):
                queries.append((end_time - start_time, query,))
            wiking.WikingDefaultDataClass.set_query_callback(query_callback)
            uri = req.uri()
            tmpfile = tempfile.NamedTemporaryFile().name
            profile.run('from wiking.handler import Handler; '
                        'self = Handler._instance; '
                        'self._result = self._handle(self._profile_req)',
                        tmpfile)
            try:
                stats = pstats.Stats(tmpfile)
                stats.strip_dirs()
                stats.sort_stats('cumulative')
                wiking.debug("Profile statistics for %s:" % (uri,))
                stats.stream = sys.stderr
                sys.stderr.write('   ')
                stats.print_stats()
                sys.stderr.flush()
            finally:
                os.remove(tmpfile)
            wiking.debug("Database queries for: %s" % (uri,))
            for q in queries:
                info = ('#' if q[0] >= 0.01 else ' ',) + q
                sys.stderr.write('   %s%0.3f %s\n' % info)
            sys.stderr.flush()
            return self._result
        else:
            #result, t1, t2 = timeit(self._handle, req)
            #log(OPERATIONAL, "Request processed in %.1f ms (%.1f ms CPU):" %
            #                  (1000*t2, 1000*t1), req.uri())
            #return result
            try:
                return self._handle(req)
            finally:
                # We can observe pending transactions in Wiking applications,
                # so let's close them all after each request.
                wiking.WikingDefaultDataClass.rollback_connections()
            
try:
    # Only for backwards compatibility with older Apache/mod_python
    # configurations which relied on the entry point to be located in this
    # module (which is no longer specific to mod_python).  If
    # mod_python_interface failed to import, we are not running under
    # mod_python.
    import mod_python_interface
    handler = mod_python_interface.ModPythonHandler()
except:
    pass
