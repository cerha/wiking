# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2017 OUI Technology Ltd.
# Copyright (C) 2019-2024 Tomáš Cerha <t.cerha@gmail.com>
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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys
import traceback
import json
import datetime

import wiking
import lcg
import pytis
import pytis.util
import pytis.data as pd
from pytis.util import OPERATIONAL, log

_ = lcg.TranslatableTextFactory('wiking')

import urllib.parse


class Handler:
    """Wiking handler.

    The handler passes the actual request processing to the current application.  Its main job is
    handling errors during this processing and dealing with its result (typically exporting the
    document into HTML and sending it to the client).

    """
    _instance = None  # Used for profiling only.

    def __init__(self, req):
        """Initialize the global wiking handler instance.

        The argument 'req' is the initial request which triggered the Handler
        creation, however the handler will normally exist much longer than for
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
        pytis.config.dblisten = False
        pytis.config.log_exclude = [pytis.util.ACTION, pytis.util.EVENT, pytis.util.DEBUG]
        for option in ('dbname', 'dbhost', 'dbport', 'dbuser', 'dbpass', 'dbsslm', 'dbschemas',):
            setattr(pytis.config, option, getattr(wiking.cfg, option))
        pytis.config.dbconnections = wiking.cfg.dbconnections
        pytis.config.dbconnection = pytis.config.option('dbconnection').default()
        pytis.config.resolver = wiking.cfg.resolver
        self._application = application = wiking.module.Application
        self._exporter = wiking.cfg.exporter(translations=wiking.cfg.translation_path)
        application.initialize(req)
        # Save the current handler instance for profiling purposes.
        Handler._instance = self

    def _resource_provider(self, req):
        styles = []
        for x in self._application.stylesheets(req):
            if isinstance(x, str):
                x = lcg.Stylesheet(x, uri=x)
            styles.append(x)
        return lcg.ResourceProvider(resources=styles, dirs=wiking.cfg.resource_path)

    def _build(self, req, document, lang):
        """Return the 'lcg.ContentNode' instance representing the given document.

        The whole application menu structure must be built in order to create
        the 'lcg.ContentNone' instance.

        """
        uri = '/' + req.uri().strip('/')
        nodes = {}
        application = self._application
        all_variants = application.languages()
        resource_provider = self._resource_provider(req)

        def mknode(item):
            # Caution - make the same uri transformation as above to get same
            # results in all cases (such as for '/').
            item_uri = '/' + item.id().strip('/')
            if item_uri == uri:
                # Note, the document title should not override the menu item title.
                # Only the main page heading is affected, but the ContentNode's
                # title matches the MenuItem's title.
                title = document.title() or item.title()
                if title and document.subtitle():
                    title = lcg.concat(title, ' :: ', document.subtitle())
                heading = lcg.TextContent(title)
                content = document.content()
                if isinstance(content, (list, tuple)):
                    content = lcg.Container([c for c in content if c is not None])
                variants = document.variants()
                if variants is None:
                    variants = item.variants()
                globals_ = document.globals()
            else:
                variants = item.variants()
                heading = None
                content = None
                globals_ = None
            if variants is None:
                variants = all_variants
            node = lcg.ContentNode(item_uri, title=item.title(), heading=heading,
                                   descr=item.descr(), content=content,
                                   variants=[lcg.Variant(v) for v in variants],
                                   active=item.active(), foldable=item.foldable(),
                                   hidden=item.hidden() or lang not in variants,
                                   children=[mknode(i) for i in item.submenu()],
                                   resource_provider=resource_provider,
                                   globals=globals_)
            nodes[item_uri] = node
            return node
        top_level_nodes = [mknode(item) for item in application.menu(req)]
        try:
            node = nodes[uri]
        except KeyError:
            # The current document's node was not created with the menu.
            # We need to create an extra node and add into the structure.
            parent = None
            pathlen = len(req.path)
            for i in range(pathlen - 1):
                # Find the parent node by the closest uri prefix.
                subpath = '/' + '/'.join(req.path[:pathlen - i - 1])
                if subpath in nodes:
                    parent = nodes[subpath]
                    break
            node = mknode(wiking.MenuItem(
                uri, hidden=True,
                title=document.title() or parent and parent.title() or None,
                variants=document.variants() or parent and parent.variants() or None,
            ))
            if parent:
                node._set_parent(parent)
                parent._children += (node,)
            else:
                top_level_nodes.append(node)
        lcg.ContentNode('__wiking_root_node__', title='root', content=lcg.Content(),
                        children=top_level_nodes)
        return node

    def _serve_document(self, req, document, status_code=200):
        """Serve a document using the Wiking exporter."""
        lang = document.lang() or req.preferred_language(raise_error=False) or 'en'
        layout = document.layout() or self._exporter.Layout.DEFAULT
        node = self._build(req, document, lang)
        context = self._exporter.context(node, lang, sec_lang=document.sec_lang(),
                                         req=req, layout=layout)
        exported = self._exporter.export(context)
        # exported, t1, t2 = timeit(self._exporter.export, context)
        # log(OPERATIONAL, "Document exported in %.1f ms (%.1f ms CPU):" %
        #                   (1000*t2, 1000*t1), req.uri())
        return req.send_response(context.localize(exported), status_code=status_code)

    def _serve_content(self, req, content):
        """Serve a document using the Wiking exporter."""
        node = lcg.ContentNode(req.uri(), content=content,
                               resource_provider=self._resource_provider(req))
        context = self._exporter.context(node, lang=req.preferred_language(), req=req)
        return req.send_response(context.localize(content.export(context)))

    def _handle_maintenance_mode(self, req):
        import http.client
        # Translators: Meaning that the system (webpage) does not work now
        # because we are updating/fixing something but will work again after
        # the maintaince is finished.
        node = lcg.ContentNode(req.uri().encode('utf-8'), title=_("Maintenance Mode"),
                               content=lcg.p(_("The system is temporarily down for maintenance.")))
        exporter = wiking.MinimalExporter(translations=wiking.cfg.translation_path)
        try:
            lang = req.preferred_language()
        except Exception:
            lang = wiking.cfg.default_language_by_domain.get(req.server_hostname(),
                                                             wiking.cfg.default_language) or 'en'
        context = exporter.context(node, lang=lang)
        exported = exporter.export(context)
        return req.send_response(context.localize(exported),
                                 status_code=http.client.SERVICE_UNAVAILABLE)

    def _handle_request_error(self, req, error):
        self._application.report_error(req, error)
        for header, value in error.headers(req):
            req.set_header(header, value)
        if req.is_api_request():
            return req.send_response(json.dumps(dict(error=error.data(req))),
                                     status_code=error.status_code(),
                                     content_type='application/json')
        else:
            document = wiking.Document(error.title(), error.content(req))
            return self._serve_document(req, document, status_code=error.status_code())

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
                # Very basic CSRF prevention
                if req.param('submit') and req.header('Referer'):
                    referer = urllib.parse.urlparse(req.header('Referer'))
                    referer_uri = referer.scheme + '://' + referer.netloc
                    server_uri = req.server_uri(current=True)
                    if referer_uri != server_uri:
                        wiking.debug("Request rejected due to CSRF protection:", referer_uri, server_uri)
                        raise wiking.Redirect(req.server_uri(current=True))
                # Regular processing starts here.
                try:
                    result = self._application.handle(req)
                except wiking.Abort as abort:
                    result = abort.result()
                if isinstance(result, (tuple, list)):
                    # Temporary backwards compatibility conversion.
                    content_type, data = result
                    result = wiking.Response(data, content_type=content_type)
                if req.is_api_request() and isinstance(result, (lcg.Content, wiking.Document)):
                    # This is a very generic detection of invalid API
                    # requests.  We just assume, that the clients, which
                    # indicate that they accept JSON responses are API
                    # clients and they are not interested in responses, which
                    # display human readable content.
                    raise wiking.BadRequest(_("This URI does not belong to server API."))
                if isinstance(result, wiking.Document):
                    # Perform authentication here if it was not performed before
                    # to handle authentication exceptions now and prevent them in
                    # export time.  When the result is a Document, we will always
                    # need to know the authenticated user in order to display the
                    # login control at the top of the page.
                    user = req.user()
                    if user:
                        password_expiration = user.password_expiration()
                        password_change_uri = wiking.module.Application.password_change_uri(req)
                        if ((password_change_uri and password_expiration and
                             password_expiration <= datetime.date.today() and
                             req.uri() != password_change_uri)):
                            req.message(_("Your password expired."), req.ERROR)
                            req.message(_("Access to the application is now restricted "
                                          "until you change your password."))
                            raise wiking.Redirect(password_change_uri)
                    return self._serve_document(req, result)
                elif isinstance(result, lcg.Content):
                    return self._serve_content(req, result)
                elif isinstance(result, wiking.Response):
                    last_modified = result.last_modified()
                    if last_modified is not None and req.cached_since(last_modified):
                        raise wiking.NotModified()
                    for header, value in result.headers():
                        req.set_header(header, value)
                    filename = result.filename()
                    if filename:
                        # When the filename contains non-ascii characters, uwsgi raises:
                        # TypeError: http header must be encodable in latin1
                        # Some context at: https://stackoverflow.com/questions/93551/
                        try:
                            filename.encode('latin-1')
                        except UnicodeEncodeError:
                            filename_info = "filename*=UTF-8''" + urllib.parse.quote(filename)
                        else:
                            filename_info = 'filename="%s"' % filename
                        disposition = 'inline' if result.inline() else 'attachment'
                        req.set_header('Content-Disposition', disposition + '; ' + filename_info)
                    return req.send_response(result.data(), content_type=result.content_type(),
                                             content_length=result.content_length(),
                                             status_code=result.status_code(),
                                             last_modified=result.last_modified())
                else:
                    raise Exception('Invalid handler result: %s' % type(result))
            except wiking.NotModified as error:
                return req.send_response('', status_code=error.status_code(), content_type=None)
            except wiking.Redirect as r:
                return req.redirect(r.uri(), r.args(), status_code=r.status_code())
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
            except wiking.ClosedConnection:
                return []
        except Exception:
            # Any other unhandled exception is an Internal Server Error.  It is
            # handled in a separate try/except block to chatch also errors in
            # except blocks of the inner level.
            return self._handle_request_error(req, wiking.InternalServerError())

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
                    # First request does a lot of unusual suff, so profiling it
                    # usually doesn't make much sense.
                    wiking.debug("Profiling disabled for the initial request.")
                    enable_profiling = False
                else:
                    wiking.debug("Profiling note: This is the initial request.")
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
            return self._handle(req)
