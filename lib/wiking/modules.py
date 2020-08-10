# -*- coding: utf-8 -*-
#
# Copyright (C) 2005-2017 OUI Technology Ltd.
# Copyright (C) 2019-2020 Tomáš Cerha <t.cerha@gmail.com>
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

"""Definition of the basic Wiking module classes."""

import datetime
import os
import re
import types
import codecs

import lcg
import wiking
from wiking import AuthenticationError, Forbidden, NotFound, Redirect

import http.client

_ = lcg.TranslatableTextFactory('wiking')


class Module:
    """Abstract base class defining the basic Wiking module."""
    _TITLE = None
    _DESCR = None

    @classmethod
    def name(cls):
        """Return module name as a string."""
        return cls.__name__

    @classmethod
    def title(cls):
        """Return human-friendly module name as a string or 'lcg.LocalizableText'."""
        return cls._TITLE or cls.__name__

    @classmethod
    def descr(cls):
        """Return brief module description as a string or 'lcg.LocalizableText'."""
        return cls._DESCR

    def __init__(self, name):
        """Initialize the instance.

        Arguments:

          name -- the real name which was resolved to this module by the
            resolver.  The resolved name may contain a full class name including
            the names of python modules where the class is defined.  The name
            returned by the method 'name()', on the other hand, is just the
            name of the class itself.

        """
        self._resolved_name = name
        # log(OPR, 'New module instance: %s[%x]' % (name, lcg.positive_id(self)))
        super(Module, self).__init__()


class RequestHandler:
    """Mix-in class for modules capable of handling requests."""

    def _base_uri(self, req):
        """Return the URI of this module as a string or None if not mapped.

        The URI is the full path to the module relative to server root.  If the module has no
        definite global path within the application, None is returned.  This method is actually
        just a shortcut to 'wiking.Request.module_uri()'.  See its documentation for more details.

        """
        return req.module_uri(self.name())

    def _authorized(self, req, **kwargs):
        """Return true iff the remote user is authorized to perform an action.

        The performed action is determined by 'kwargs'.  Their meaning,
        however, is not further specified in this class (it only defines the
        common interface).  Derived classes may define the meaning of `kwargs'
        more exactly.

        This class passes no 'kwargs', so it only allows checking of access to
        the module itself (calling its 'handle()' method), with no further
        resolution.

        The default implementation always returns true.

        """
        return True

    def _authorize(self, req, **kwargs):
        """Check authorization and raise error if the user has no rights to perform the action.

        Raises: `AuthenticationError' if the user is not authenticated (logged
        in) and authentication is required for given action or
        `AuthorizationError' if the user is logged in, but his rights are not
        sufficient for the action.

        The meaning of keyword arguments is the same as in the '_authorized()'
        method.

        """
        if not self._authorized(req, **kwargs):
            if not req.user():
                raise AuthenticationError()
            else:
                self._authorization_error(req, **kwargs)

    def _authorization_error(self, req, **kwargs):
        raise wiking.AuthorizationError()

    def _handle(self, req):
        raise Exception("Method '_handle()' not implemented.")

    def handle(self, req):
        """Handle the request and return the result.

        The return value may be either 'wiking.Response' instance representing
        directly the HTTP response data and headers or a 'wiking.Document'
        instance, which is later automatically converted to a 'wiking.Response'
        by 'wiking.Handler' by exporting the document into HTML using a
        'wiking.Exporter'.

        The method may also raise 'RequestError' exceptions to indicate special
        states or 'Redirect' exceptions to perform HTTP redirection.

        This method only performs authorization check and postpones further
        processing to '_handle()' method.  Please, never override this method
        (unless you want to bypass the authorization checking).  Override
        '_handle()' instead.  The rules for the returned value are the same.

        """
        self._authorize(req)
        return self._handle(req)


class ActionHandler(RequestHandler):
    """Mix-in class for modules providing ``actions'' to handle requests.

    The actions are handled by implementing public methods named `action_*',
    where the asterisk is replaced by the action name.  The request parameter
    'action' denotes which action will be used to handle the request.  Each
    action must accept the 'wiking.Request' instance as the first argument, but
    it may also require additional arguments.  The dictionary of additional
    arguments is constructed by the method '_action_args()' depending on the
    request.  When the request doesn't provide the information needed to
    construct all the arguments for the action, the action call will
    automatically fail.  This approach may be legally used to make sure that
    the request contains all the necessary information for calling the action.

    If the request parameter 'action' is not defined, the method
    '_default_action()' will be used to find out which action should be used.

    """

    def _action_args(self, req):
        """Return the dictionary of additional action arguments."""
        return {}

    def _default_action(self, req, **kwargs):
        """Return the name of the default action as a string."""
        return None

    def _action(self, req, **kwargs):
        if req.has_param('action'):
            return req.param('action')
        else:
            return self._default_action(req, **kwargs)

    def _authorized(self, req, action, **kwargs):
        return False

    def _handle(self, req, action, **kwargs):
        """Perform action authorization and call the action method."""
        self._authorize(req, action=action, **kwargs)
        method = getattr(self, 'action_' + action)
        return method(req, **kwargs)

    def handle(self, req):
        kwargs = self._action_args(req)
        action = self._action(req, **kwargs)
        return self._handle(req, action, **kwargs)


class Documentation(Module, RequestHandler):
    """Serve the on-line documentation.

    This module is not bound to a data object.  It serves on-line documentation directly from files
    on the disk.

    By default, the first component of unresolved path refers to the key of
    `wiking.cfg.doc_dirs' which determines the base directory, where the
    documents are searched.  The rest of unresolved path refers to the actual
    file within this directory.  Filename extension and language variant is
    added automatically.

    For example a request to '/doc/wiking/user/navigation' is resolved as follows:
      * 'doc' must be mapped within application to the `Documentation' module.
      * 'wiking' is searched in `wiking.cfg.doc_dirs', where it translates for example to
        '/usr/local/share/wiking/doc/src'.
      * File '/usr/local/share/wiking/doc/src/user/navigation.<lang>.txt'. is searched,
        where <lang> may be one of the application defined languages.  Prefered language
        is determined through `Request.preferred_language()'.

    """

    def _documentation_directory(self, component):
        try:
            basedir = wiking.cfg.doc_dirs[component]
        except KeyError:
            wiking.log(wiking.OPR, "Component '%s' not found in 'wiking.cfg.doc_dirs':" % component,
                       wiking.cfg.doc_dirs)
            raise NotFound()
        if not os.path.exists(basedir):
            raise Exception("Documentation directory for '%s' does not exist. "
                            "Please check 'doc_dirs' configuration option." % component)
        return basedir

    def _document_path(self, req):
        """Return full filesystem path of document given by list of relative path components."""
        if not req.unresolved_path:
            raise Forbidden()
        component, relpath = req.unresolved_path[0], req.unresolved_path[1:]
        return os.path.join(self._documentation_directory(component), *relpath)

    def _variants(self, path):
        variants = [lang for lang in wiking.module.Application.languages()
                    if os.path.exists('.'.join((path, lang, 'txt')))]
        if not variants and os.path.exists('.'.join((path, 'en', 'txt'))):
            # HACK: Try fallback to English if no application language variants
            # are available.  In fact, the application should never return
            # content in any other language, than what is defined by
            # `Application.languages()', but default Wiking documentation is
            # often not translated to application languages and users get a
            # confusing error.  This should avoid the confusion, but a proper
            # solution would be to have all documentation files translated at
            # least to one application language.
            variants = ['en']
        return variants

    def _content(self, path, lang):
        filename = '.'.join((path, lang, 'txt'))
        f = codecs.open(filename, encoding='utf-8')
        text = "".join(f.readlines())
        f.close()
        content = lcg.Parser().parse(text)
        if len(content) == 1 and isinstance(content[0], lcg.Section):
            title = content[0].title()
            content = content[0].content()
        else:
            title = None
        return title, lcg.Container(content)

    def _handle(self, req):
        # TODO: the documentation should be processed by LCG first into some
        # reasonable output format.  Now we just search the file in all the
        # source directories and format it.
        path = self._document_path(req)
        variants = self._variants(path)
        if variants:
            del req.unresolved_path[:]
        else:
            raise NotFound()
        lang = req.preferred_language(variants)
        title, content = self._content(path, lang)
        if title is None:
            title = ' :: '.join(req.unresolved_path)
        if req.param('framed') == '1':
            # Used to display contextual help in an iframe (see pytis-ckeditor.js).
            layout = wiking.Exporter.Layout.FRAME
        else:
            layout = None
        return wiking.Document(title, content, lang=lang, variants=variants, layout=layout)

    def document_content(self, component, uri, lang):
        """Return the content of the document given by its relative URI."""
        path = os.path.join(self._documentation_directory(component), *uri.split('/'))
        return self._content(path, lang)


class Resources(Module, RequestHandler):
    """Serve the resource files as provided by the LCG's 'ResourceProvider'.

    This module will automatically serve all resources found within the
    directories configured through the 'resource_path' option.  Use with
    caution, since this module will expose all files located within configured
    directories to the internet!  Note that the LCG's default resource
    directory (as configured within the LCG package) is always automatically
    added to the search path.

    Map the module to a particular URI within your application to use it.

    """
    _MATCHER = re.compile(r"\$(\w[\w-]*)(?:\.(\w[\w-]*))?")
    _DEFAULT_THEME_MTIME = datetime.datetime.utcnow()

    def __init__(self, *args, **kwargs):
        super(Resources, self).__init__(*args, **kwargs)
        self._provider = lcg.ResourceProvider(dirs=wiking.cfg.resource_path)

    def _theme(self, req):
        """Return the color theme to be used for stylesheet color substitution.

        Returns a tuple of (theme, timestamp), where theme is a 'wiking.Theme'
        instance and timestamp is a timezone naive 'datetime.datetime' instance
        in UTC representing the last modification time of the theme or None
        when unknown.  It should not be None to support HTTP client side
        caching when serving stylesheets.  If None, caching can not be used
        which means that all stylesheets will be unnecessarily sent again for
        every page request.

        'wiking.cfg.theme' is returned by default but may be overriden to
        select the current theme based on some application specific logic
        (eg. according to user's preferences, etc.).

        """
        return wiking.cfg.theme, self._DEFAULT_THEME_MTIME

    def _substitute(self, stylesheet, theme):
        def subst(match):
            name, key = match.groups()
            value = theme[name]
            if key:
                value = value[key]
            return value
        return self._MATCHER.sub(subst, stylesheet)

    def _handle_resource(self, req, filename):
        subdir = filename.split('/', 1)[0]
        if subdir in ('images', 'css', 'scripts', 'media', 'flash'):
            # This is just a temporary hack to allow backward compatibility
            # with resource URIs using type specific subdirectories.
            # Wiking no longer generates such URIs and applications should
            # avoid them too as this hack will be removed in future.
            filename = filename[len(subdir) + 1:]
        else:
            subdir = None
        resource = self._provider.resource(filename)
        if resource and resource.src_file() and (subdir is None or resource.SUBDIR == subdir):
            return wiking.serve_file(req, resource.src_file(),
                                     allow_redirect=not filename.endswith('.css'))
        else:
            raise NotFound()

    def _handle(self, req):
        """Serve the resource from a file."""
        if len(req.unresolved_path) < 1 or '..' in req.unresolved_path:
            # Avoid direcory traversal attacks.
            raise Forbidden()
        filename = os.path.join(*req.unresolved_path)
        response = self._handle_resource(req, filename)
        if response.status_code() == http.client.OK and filename.endswith('.css'):
            # Substitute the current color theme in stylesheets.
            theme, theme_mtime = self._theme(req)
            stylesheet_mtime = response.last_modified()
            if stylesheet_mtime and theme_mtime:
                mtime = max(stylesheet_mtime, theme_mtime)
                if req.cached_since(mtime):
                    raise wiking.NotModified()
            else:
                mtime = None
            data = response.data()
            if isinstance(data, (list, types.GeneratorType)):
                data = b''.join(data)
            if isinstance(data, bytes):
                data = str(data, 'utf-8')
            data = self._substitute(data, theme)
            response = wiking.Response(data, content_type=response.content_type(),
                                       last_modified=mtime, filename=response.filename(),
                                       headers=response.headers())
        max_age = wiking.cfg.resource_client_cache_max_age
        if ((max_age is not None and response.last_modified() is not None
             and 'Cache-Control' not in dict(response.headers()))):
            response.add_header('Cache-Control', 'max-age=%d' % max_age)
        return response

    def resource(self, filename):
        """Obtain a 'lcg.Resource' instance from the global resource provider.

        This method may be useful when you need to search resources in wiking
        module's code.  Otherwise the resource provider is only available in
        export time through the export context.

        """
        return self._provider.resource(filename)

    def resource_provider(self):
        """Return the global resource provider as 'lcg.ResourceProvider' instance."""
        return self._provider


class SiteIcon(Module, RequestHandler):
    """Serve site icon according to the configuration option 'site_icon'.

    This module is mapped to '/favicon.ico' in the default 'Application'.

    """

    def _handle(self, req):
        filename = wiking.cfg.site_icon
        if filename:
            return wiking.serve_file(req, filename, 'image/vnd.microsoft.icon')
        else:
            raise NotFound()


class Robots(Module, RequestHandler):
    """Serve robots.txt according to configuration.

    This module is mapped to '/robots.txt' in the default 'Application'.

    The file currently only supports the 'Crawl-delay' directive.  It is not
    served (returns 404) when the configuration option 'crawl_delay' is None.

    """

    def _handle(self, req):
        crawl_delay = wiking.cfg.crawl_delay
        if crawl_delay is not None:
            data = ("User-agent: *\n"
                    "Crawl-delay: %d\n" % crawl_delay)
            return wiking.Response(data, 'text/plain')
        else:
            raise NotFound()


class SubmenuRedirect(Module, RequestHandler):
    """Handle all requests by redirecting to the first submenu item.

    This class may become handy if you don't want the root menu items to have their own content,
    but rather redirect the user to the first submenu item available

    """

    def _handle(self, req):
        def find(items, id):
            for item in items:
                if item.id() == id:
                    return item
                else:
                    item = find(item.submenu(), id)
                    if item:
                        return item
            return None
        id = req.path[0]
        item = find(wiking.module.Application.menu(req), id)
        if item:
            if item.submenu():
                raise Redirect('/' + item.submenu()[0].id())
            else:
                raise Exception("Menu item '%s' has no childs." % id)
        else:
            raise Exception("Menu item for '%s' not found." % id)


class Session(Module):
    """Session management module abstract interface.

    The 'Session' module is used by 'AuthenticationProvider' implementations to
    persist session state between requests on the server side.

    The implementations of this abstract interface must implement the methods
    'init()', 'check()' and 'close()'.

    """

    def init(self, req, user, auth_type, reuse=False):
        """Begin new session for given user with given session key.

        Arguments:
          req -- current request object as 'wiking.Request' instance
          user -- successfully authenticated user as 'wiking.User' instance
          auth_type -- Short string describing the authentication method.  Each
            'wiking.AuthenticationProvider' subclass uses its specific string,
            such as "Cookie" for 'wiking.CookieAuthenticationProvider' etc.
          reuse -- If true, try to reuse the existing session for the same
            'auth_type'.  This is a work around for authentication methods
            which can't remember the session key client side and thus 'check()'
            can not be used.  If a a currently active session for the same
            'user' with the same 'auth_type' exists, it is reused without
            checking the session key.  Such session is extended as if 'check()'
            was called and None is returned from this method to indicate this
            case.  This means that there can be just one active session for the
            same user and given 'auth_type' at the same time.

        The method is responsible for creation of a new session key and
        persistently storing its association with given user to allow checking
        validity of this session key during upcoming requests.

        The caller is responsible for passing the returned session key to the
        client and checking its validity using 'check()' on client's next
        request with the same session key or closing this session using
        'close()'.

        Returns the new session key as a string or None if 'reuse' was true and
        existing session has been reused.

        """
        return None

    def check(self, req, session_key):
        """Return the session user if session_key matches an active session.

        Arguments:
          req -- current request object as 'wiking.Request' instance
          session_key -- The session key previously returned by 'init()'.

        Extend the session lifetime if the check is succesful.

        Returns a 'wiking.User' instance or None.

        """
        return False

    def close(self, req, session_key):
        """Remove persistent session information and clean-up after user logged out."""
        pass


class Search(Module, ActionHandler):

    _SEARCH_TITLE = _("Searching")
    _RESULT_TITLE = _("Search results")
    _EMPTY_SEARCH_MESSAGE = _("Given search term doesn't contain any searchable term.")

    class SearchForm(lcg.Content):

        _SEARCH_FIELD_LABEL = _("Search words:")
        _SEARCH_BUTTON_LABEL = _("Search")

        def __init__(self, req):
            lcg.Content.__init__(self)
            self._uri = req.uri()

        def export(self, exporter):
            g = exporter.generator()
            return g.form(method='POST', action=self._uri, contents=(
                g.label(self._SEARCH_FIELD_LABEL, 'input'), ' ',
                g.input(name='input', id='input', tabindex=0, size=20),
                g.br(),
                g.submit(self._SEARCH_BUTTON_LABEL, cls='submit'),
                g.hidden(name='action', value='search'),
            ))

    class Result:

        def __init__(self, uri, title, sample=None):
            self._title = title
            self._sample = sample
            self._uri = uri

        def uri(self):
            return self._uri

        def title(self):
            return self._title

        def sample(self):
            return self._sample

    def _search_form(self, req, message=None):
        content = []
        if message is not None:
            content.append(lcg.p(message))
        content = [self.SearchForm(req)]
        return wiking.Document(self._SEARCH_TITLE, lcg.Container(content))

    def _transform_input(self, input):
        input = re.sub('[&|!()"\'\\\\]', ' ', input)
        input = input.strip()
        input = re.sub(' +', '&', input)
        return input

    def _perform_search(self, expression, req):
        return ()

    def _result_item(self, item):
        sample = item.sample()
        link = lcg.link(item.uri(), label=item.title(), descr=sample,)
        if sample is None:
            result_item = lcg.p((link,))
        else:
            result_item = lcg.dl(((link, sample),))
        return result_item

    def _empty_result_page(self):
        return lcg.p(_("Nothing found."))

    def _result_page(self, req, result):
        if result:
            content = lcg.Container([self._result_item(item) for item in result])
        else:
            content = self._empty_result_page()
        return wiking.Document(self._RESULT_TITLE, content)

    # Actions

    def _default_action(self, req, **kwargs):
        return 'view'

    def action_view(self, req, **kwargs):
        return self._search_form(req)

    def action_search(self, req, **kwargs):
        input = req.param('input', '')
        expression = self._transform_input(input)
        if not expression:
            return self._search_form(req, message=self._EMPTY_SEARCH_MESSAGE)
        result = self._perform_search(expression, req)
        return self._result_page(req, result)


class Reload(Module):

    _UNRELOADABLE_MODULES = ('sys', '__main__', '__builtin__',)
    # NOTE: Wiking and LCG are not reloadable due to the mess in Python class
    # instances  after reload.
    _RELOADABLE_REGEXP = '.*/wikingmodules/.*'

    def __init__(self, *args, **kwargs):
        super(Reload, self).__init__(*args, **kwargs)
        self._reloadable_regexp = re.compile(self._RELOADABLE_REGEXP)

    def _module_reloadable(self, name, module, req):
        return (module is not None and
                name not in self._UNRELOADABLE_MODULES and
                hasattr(module, '__file__') and
                self._reloadable_regexp.match(module.__file__))

    def _reload_modules(self, req):
        import sys
        module_names = []
        for name, module in sys.modules.items():
            if self._module_reloadable(name, module, req):
                try:
                    reload(module)
                    module_names.append(name)
                except Exception:
                    pass
        return module_names

    def _handle(self, req):
        module_names = self._reload_modules(req)
        content = lcg.coerce((lcg.p(_("The following modules were successfully reloaded:")),
                              lcg.p(", ".join(module_names)),))
        return wiking.Document(_("Reload"), lcg.coerce(content))
