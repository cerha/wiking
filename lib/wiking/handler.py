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

import re

import wiking
import lcg

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
                        log(OPR, "Invalid numeric value for '%s':" % name, value)
                        continue
                elif isinstance(option, wiking.cfg.BooleanOption):
                    if value.lower() in ('yes', 'true', 'on'):
                        value = True
                    elif value.lower() in ('no', 'false', 'off'):
                        value = False
                    else:
                        log(OPR, "Invalid boolean value for '%s':" % name, value)
                        continue
                elif not isinstance(option, wiking.cfg.StringOption):
                    log(OPR, "Unable to set '%s' through request options." % name)
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
            setattr(config, option, getattr(cfg, option))
        config.dbconnections = wiking.cfg.connections
        config.dbconnection = config.option('dbconnection').default()
        config.resolver = wiking.cfg.resolver
        del config
        self._application = application = wiking.module('Application')
        self._exporter = wiking.cfg.exporter(translations=wiking.cfg.translation_path)
        application.initialize(config_file)
        # Save the current handler instance for profiling purposes.
        Handler._instance = self 


    def _build(self, req, document):
        """Return the 'WikingNode' instance representing the given document.

        The whole application menu structure must be built in order to create
        the 'WikingNone' instance ('WikingNode' is derived from
        'lcg.ContentNode').
        
        """
        application = self._application
        uri = '/'+req.uri().strip('/')
        lang = document.lang() or req.preferred_language(raise_error=False) or 'en'
        nodes = {}
        styles = []
        for x in application.stylesheets(req):
            if isinstance(x, basestring):
                x = lcg.Stylesheet(x, uri=x)
            styles.append(x)
        resource_provider = lcg.ResourceProvider(resources=styles, dirs=wiking.cfg.resource_path)
        def mknode(item):
            # Caution - make the same uri transformation as above to get same
            # results in all cases (such as for '/').
            item_uri = '/'+item.id().strip('/') 
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
            node = WikingNode(item_uri.encode('utf-8'), title=item.title(), page_heading=heading,
                              descr=item.descr(), content=content,
                              lang=lang, sec_lang=document.sec_lang(), variants=variants or (),
                              active=item.active(), foldable=item.foldable(), hidden=hidden,
                              children=[mknode(i) for i in item.submenu()],
                              resource_provider=resource_provider, globals=document.globals(),
                              panels=panels, layout=document.layout())
            nodes[item_uri] = node
            return node
        top_level_nodes = [mknode(item) for item in application.menu(req)]
        # Find the parent node by the identifier prefix.
        parent = None
        for i in range(len(req.path)-1):
            key = '/'+'/'.join(req.path[:len(req.path)-i-1])
            if key in nodes:
                parent = nodes[key]
                break
        try:
            node = nodes[uri]
        except KeyError:
            # Create the current document's node if it was not created with the menu.
            variants = document.variants() or parent and parent.variants() or None
            node = mknode(MenuItem(uri, document.title(), hidden=True, variants=variants))
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

    def _error_log_variables(self, req, error):
        return dict(
            error_type=error.__class__.__name__,
            server_hostname=req.server_hostname(),
            uri=req.uri(),
            abs_uri=req.server_uri(current=True) + req.uri(),
            user=(req.user() and req.user().login() or 'anonymous'),
            remote_host=req.remote_host(),
            referer=req.header('Referer'),
            user_agent=req.header('User-Agent'),
            server_software='Wiking %s, LCG %s, Pytis %s' % \
                (wiking.__version__, lcg.__version__, pytis.__version__),
            )
    
    def _handle_request_error(self, req, error):
        if not isinstance(error, (wiking.AuthenticationError,
                                  wiking.Abort, wiking.DisplayDocument)):
            variables = self._error_log_variables(req, error)
            message = wiking.cfg.log_format % variables
            if wiking.cfg.debug:
                frames = ['%s:%d:%s()' % tuple(frame[1:4]) for frame in error.stack()]
                message += " (%s)" % ", ".join(reversed(frames))
            if isinstance(error, InternalServerError):
                message += ' ' + error.buginfo()
            log(OPR, message)
        document = wiking.Document(error.title(req), error.content(req))
        return self._serve_document(req, document, status_code=error.status_code(req))

    def _send_bug_report(self, req, einfo, error, address):
        from xml.sax import saxutils
        import cgitb, traceback
        def param_value(param):
            if param in ('passwd', 'password'):
                value = '<password hidden>'
            else:
                value = req.param(param)
            if not isinstance(value, basestring):
                value = str(value)
            lines = value.splitlines()
            if len(lines) > 1:
                value = lines[0][:40] + '... (trimmed; total %d lines)' % len(lines)
            elif len(value) > 40:
                value = value[:40] + '... (trimmed; total %d chars)' % len(value)
            return saxutils.escape(value)
        def format_info(label, value):
            if value and (value.startswith('http://') or value.startswith('https://')):
                value = '<a href="%s">%s</a>' % (value, value)
            return "%s: %s\n" % (label, value)
        variables = self._error_log_variables(req, error)
        req_info = (
            ("URI", variables['abs_uri']),
            ("Remote host", variables['remote_host']),
            ("Remote user", variables['user']),
            ("HTTP referer", variables['referer']),
            ("User agent", variables['user_agent']),
            ('Server software', variables['server_software']),
            ("Request parameters", "\n"+
             "\n".join(["  %s = %s" % (saxutils.escape(param), param_value(param))
                        for param in req.params()])),
            )
        def escape(text):
            if isinstance(text, basestring):
                return re.sub(r'[^\x01-\x7F]', '?', text)
            elif isinstance(text, (tuple, list,)):
                return [escape(t) for t in text]
            else:
                return escape(str(t))
        try:
            text = ("\n".join(["%s: %s" % pair for pair in req_info]) + "\n\n" +
                    cgitb.text(einfo))
        except UnicodeDecodeError:
            text = ("\n".join(["%s: %s" % (label, escape(value),) for label, value in req_info]) + "\n\n" +
                    cgitb.text(escape(einfo)))
        try:
            html = ("<html><pre>" +
                    "".join([format_info(label, value) for label, value in req_info]) +"\n\n"+
                    "".join(traceback.format_exception(*einfo)) +
                    "</pre>"+
                    cgitb.html(einfo) +"</html>")
        except UnicodeDecodeError:
            html = ("<html><pre>" +
                    "".join([format_info(label, escape(value)) for label, value in req_info]) +"\n\n"+
                    "".join(traceback.format_exception(*einfo)) +
                    "</pre>"+
                    cgitb.html(escape(einfo)) +"</html>")            
        subject = 'Wiking Error: ' + error.buginfo()
        err = send_mail(address, subject, text, html=html,
                        headers=(('Reply-To', address),
                                 ('X-Wiking-Bug-Report-From', wiking.cfg.server_hostname)))
        if err:
            log(OPR, "Failed sending exception info to %s:" % address, err)
        else:
            log(OPR, "Traceback sent to %s." % address)
    
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
                if isinstance(result, wiking.Document):
                    # Always perform authentication (if it was not performed before) to handle
                    # authentication exceptions here and prevent them in export time.
                    req.user()
                    return self._serve_document(req, result)
                elif isinstance(result, wiking.Response):
                    for header, value in result.headers():
                        req.set_header(header, value)
                    filename = result.filename()
                    if filename:
                        req.set_header('Content-Disposition',
                                       'attachment; filename="%s"' % filename)
                    return req.send_response(result.data(), content_type=result.content_type(),
                                             content_length=result.content_length(),
                                             status_code=result.status_code())
                else:
                    raise Exception('Invalid wiking handler result: %s' % type(result))
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
            error = InternalServerError(einfo)
            address = wiking.cfg.bug_report_address
            if address is not None:
                self._send_bug_report(req, einfo, error, address)
            if not wiking.cfg.debug:
                # When debug is on, the full traceback goes to the browser
                # window and it is better to leave the error log for printing
                # debugging information (the exception makes too much noise
                # there...) so we log the traceback only when debug is off.
                try:
                    # cgitb sometimes fails when the introspection touches
                    # something sensitive, such as database objects.
                    import cgitb
                    tb = cgitb.text(einfo)
                except:
                    import traceback
                    tb = "".join(traceback.format_exception(*einfo))
                log(OPR, "\n"+ tb)
            return self._handle_request_error(req, error)
            
    def handle(self, req):
        if wiking.cfg.debug and req.param('profile') == '1':
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
