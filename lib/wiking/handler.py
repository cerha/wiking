# Copyright (C) 2006, 2007, 2008, 2009, 2010, 2011, 2012 Brailcom, o.p.s.
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

import wiking
import lcg
import types

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
        cfg = wiking.cfg
        config_file = req.option('config_file')
        if config_file:
            # Read the configuration file first, so that the request options have a higher priority.
            cfg.user_config_file = config_file
        for option in cfg.options():
            name = option.name()
            value = req.option(name)
            if value and name != 'config_file':
                if name in ('translation_path', 'resource_path', 'modules'):
                    separator = value.find(':') != -1 and ':' or ','
                    value = tuple([d.strip() for d in value.split(separator)])
                    if name == 'translation_path':
                        value = tuple(cfg.translation_path) + value
                    elif name == 'resource_path':
                        value += tuple(cfg.resource_path)
                elif isinstance(option, cfg.NumericOption):
                    if value.isdigit():
                        value = int(value)
                    else:
                        log(OPR, "Invalid numeric value for '%s':" % name, value)
                        continue
                elif isinstance(option, cfg.BooleanOption):
                    if value.lower() in ('yes', 'true', 'on'):
                        value = True
                    elif value.lower() in ('no', 'false', 'off'):
                        value = False
                    else:
                        log(OPR, "Invalid boolean value for '%s':" % name, value)
                        continue
                elif not isinstance(option, cfg.StringOption):
                    log(OPR, "Unable to set '%s' through request options." % name)
                    continue
                setattr(cfg, name, value)
        # Apply default values which depend on the request.
        server_hostname = cfg.server_hostname
        if server_hostname is None:
            # TODO: The name returned by req.server_hostname() works for simple
            # cases where there are no server aliases, but we can not guarantee
            # that it is really unique.  Thus might be safer to raise an error
            # when req.primary_server_hostname() returns None and require
            # configuring server_hostname explicitly.
            server_hostname = req.primary_server_hostname() or req.server_hostname()
            cfg.server_hostname = server_hostname
        domain = server_hostname
        if domain.startswith('www.'):
            domain = domain[4:]
        if cfg.webmaster_address is None:
            cfg.webmaster_address = 'webmaster@' + domain
        if cfg.default_sender_address is None:
            cfg.default_sender_address = 'wiking@' + domain
        if cfg.dbname is None:
           cfg.dbname = server_hostname
        if cfg.resolver is None:
            cfg.resolver = wiking.WikingResolver(cfg.modules)
        # Modify pytis configuration.
        import pytis.util
        import config
        config.dblisten = False
        config.log_exclude = [pytis.util.ACTION, pytis.util.EVENT, pytis.util.DEBUG]
        for option in ('dbname', 'dbhost', 'dbport', 'dbuser', 'dbpass', 'dbsslm', 'dbschemas',):
            setattr(config, option, getattr(cfg, option))
        config.dbconnections = cfg.connections
        config.dbconnection = config.option('dbconnection').default()
        config.resolver = cfg.resolver
        del config
        self._application = wiking.module('Application')
        self._exporter = cfg.exporter(translations=cfg.translation_path)
        # Save the current handler instance for profiling purposes.
        Handler._instance = self 


    def _build(self, req, document):
        """Return the 'WikingNode' instance representing the given document.

        The whole application menu structure must be built in order to create
        the 'WikingNone' instance ('WikingNode' is derived from
        'lcg.ContentNode').
        
        """
        application = self._application
        id = '/'.join(req.path)
        lang = document.lang() or req.preferred_language(raise_error=False) or 'en'
        nodes = {}
        styles = []
        for x in application.stylesheets(req):
            if isinstance(x, basestring):
                x = lcg.Stylesheet(x, uri=x)
            styles.append(x)
        resources = tuple(styles) + document.resources()
        resource_provider = lcg.ResourceProvider(resources=resources, dirs=cfg.resource_path)
        def mknode(item):
            if item.id() == id:
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
            node = WikingNode(item.id().encode('utf-8'), title=item.title(), page_heading=heading,
                              descr=item.descr(), content=content,
                              lang=lang, sec_lang=document.sec_lang(), variants=variants or (),
                              active=item.active(), foldable=item.foldable(), hidden=hidden,
                              children=[mknode(i) for i in item.submenu()],
                              resource_provider=resource_provider, globals=document.globals(),
                              panels=panels, layout=document.layout())
            nodes[item.id()] = node
            return node
        top_level_nodes = [mknode(item) for item in application.menu(req)]
        # Find the parent node by the identifier prefix.
        parent = None
        for i in range(len(req.path)-1):
            key = '/'.join(req.path[:len(req.path)-i-1])
            if key in nodes:
                parent = nodes[key]
                break
        if id in nodes:
            node = nodes[id]
        else: 
            # Create the current document's node if it was not created with the menu.
            variants = document.variants() or parent and parent.variants() or None
            node = mknode(MenuItem(id, document.title(), hidden=True, variants=variants))
            if parent:
                parent.add_child(node)
            else:
                top_level_nodes.append(node)
        root = WikingNode('__wiking_root_node__', title='root', content=lcg.Content(),
                          children=top_level_nodes)
        return node

    def _serve_document(self, req, document, status_code=200):
        """Serve a document using the Wiking exporter."""
        node = self._build(req, document)
        context = self._exporter.context(node, node.lang(), sec_lang=node.sec_lang(), req=req)
        exported = self._exporter.export(context)
        return req.send_response(context.localize(exported), status_code=status_code)

    def _serve_error_document(self, req, error):
        """Serve an error page using the Wiking exporter."""
        error.log(req)
        document = wiking.Document(error.title(req), error.message(req))
        return self._serve_document(req, document, status_code=error.status_code(req))

    def _serve_minimal_error_document(self, req, error):
        """Serve a minimal error page using the minimalistic exporter."""
        error.log(req)
        node = lcg.ContentNode(req.uri().encode('utf-8'),
                               title=error.title(req),
                               content=error.message(req))
        exporter = wiking.MinimalExporter(translations=wiking.cfg.translation_path)
        try:
            lang = req.preferred_language()
        except:
            lang = wiking.cfg.default_language_by_domain.get(req.server_hostname(),
                                                             wiking.cfg.default_language) or 'en'
        context = exporter.context(node, lang=lang)
        exported = exporter.export(context)
        return req.send_response(context.localize(exported), status_code=error.status_code(req))

    def _handle(self, req):
        application = self._application
        try:
            try:
                result = application.handle(req)
                if isinstance(result, wiking.Document):
                    # Always perform authentication (if it was not performed before) to handle
                    # authentication exceptions here and prevent them in export time.
                    req.user()
                    return self._serve_document(req, result)
                elif isinstance(result, tuple):
                    content_type, data = result
                    return req.send_response(data, content_type=content_type)
                elif isinstance(result, (list, types.GeneratorType)):
                    return result
                else:
                    raise Exception('Invalid wiking handler result: %s' % type(result))
            except wiking.RequestError as error:
                try:
                    req.user()
                except wiking.RequestError:
                    # Ignore all errors within authentication except for AuthenticationError.
                    pass
                except wiking.AuthenticationError as auth_error:
                    return self._serve_error_document(req, auth_error)
                return self._serve_error_document(req, error)
            except (wiking.ClosedConnection, wiking.Redirect):
                raise
            except wiking.DisplayDocument as e:
                return self._serve_document(req, e.document())
            except Exception as e:
                # Try to return a nice error document produced by the exporter.
                try:
                    return application.handle_exception(req, e)
                except wiking.RequestError as error:
                    return self._serve_error_document(req, error)
        except wiking.ClosedConnection:
            return []
        except wiking.Redirect as r:
            return req.redirect(r.uri(), args=r.args(), permanent=r.permanent())
        except wiking.DisplayDocument as e:
            return self._serve_document(req, e.document())
        except Exception as e:
            # If error document export fails, return a minimal error page.  It is reasonable to
            # assume, that if RequestError handling fails, somethong is wrong with the exporter and
            # error document export will fail too, so it is ok, to have them handled both at the
            # same level above.
            try:
                return application.handle_exception(req, e)
            except wiking.RequestError as error:
                return self._serve_minimal_error_document(req, error)
            
    def handle(self, req):
        if cfg.debug and req.param('profile') == '1':
            import cProfile as profile, pstats, tempfile
            self._profile_req = req
            tmpfile = tempfile.NamedTemporaryFile().name
            profile.run('from wiking.handler import Handler; '
                        'self = Handler._instance; '
                        'self._result = self._handle(self._profile_req)',
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
            return self._result
        else:
            #result, t1, t2 = timeit(self._handle, req)
            #log(OPR, "Request processed in %.1f ms (%.1f ms wall time):" % (1000*t1, 1000*t2), req.uri())
            return self._handle(req)
            
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
