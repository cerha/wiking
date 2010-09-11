# Copyright (C) 2005, 2006, 2007, 2008, 2009, 2010 Brailcom, o.p.s.
# Author: Tomas Cerha.
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

"""Definition of the basic Wiking module classes."""

_ = lcg.TranslatableTextFactory('wiking')

class Module(object):
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

    def __init__(self, resolver, **kwargs):
        """Initialize the instance.

        Arguments:

          resolver -- a 'WikingResolver' instance.

        """
        assert isinstance(resolver, WikingResolver), resolver
        self._resolver = resolver
        #log(OPR, 'New module instance: %s[%x]' % (self.name(), lcg.positive_id(self)))
        super(Module, self).__init__(**kwargs)

    def _module(self, name, **kwargs):
        return self._resolver.wiking_module(name, **kwargs)

    
class RequestHandler(object):
    """Mix-in class for modules capable of handling requests."""
    
    def __init__(self, *args, **kwargs):
        self._application = self._module('Application')
        super(RequestHandler, self).__init__(*args, **kwargs)
    
    def _base_uri(self, req):
        """Return the URI of this module as a string or None if not mapped.

        The URI is the full path to the module relative to server root.  If the module has no
        definite global path within the application, None is returned.  This method is actually
        just a shortcut to 'WikingRequest.module_uri()'.  See its documentation for more details.

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

        The base implementation of this method postpones the authorization to
        the current wiking application by calling
        'wiking.Application.authorize()'.  This allows implementation of a
        custom authorization mechanism by an application without overriding all
        modules.  The application, however, may still choose to override this
        method in its modules to implement authorization checking for them
        directly (making it not possible to override this behavior by
        overriding the application).

        """
        return self._application.authorize(req, self, **kwargs)
    
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
                raise AuthorizationError()

    def _handle(self, req):
        raise Exception("Method '_handle()' not implemented.")
        
    def handle(self, req):
        """Handle the request and return the result.

        The result may be either a 'Document' instance or a pair (MIME_TYPE, DATA).  The document
        instance will be exported into HTML, the MIME data will be served directly.

        This method only performs authorization check and postpones further processing to
        '_handle()' method.  Please, never override this method (unless you want to bypass the
        authorization checking).  Override '_handle()' instead.  The rules for the returned value
        are the same.

        """
        self._authorize(req)
        return self._handle(req)


class ActionHandler(RequestHandler):
    """Mix-in class for modules providing ``actions'' to handle requests.

    The actions are handled by implementing public methods named `action_*',
    where the asterisk is replaced by the action name.  The request parameter
    'action' denotes which action will be used to handle the request.  Each
    action must accept the 'WikingRequest' instance as the first argument, but
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

    def _handle(self, req, action, **kwargs):
        """Perform action authorization and call the action method."""
        self._authorize(req, action=action, **kwargs)
        method = getattr(self, 'action_'+ action)
        return method(req, **kwargs)

    def handle(self, req):
        kwargs = self._action_args(req)
        action = self._action(req, **kwargs)
        return self._handle(req, action, **kwargs)


class Documentation(Module, RequestHandler):
    """Serve the on-line documentation.

    This module is not bound to a data object.  It serves on-line documentation directly from files
    on the disk.

    By default, the first component of unresolved path refers to the key of `cfg.doc_dirs' which
    determines the base directory, where the documents are searched.  The rest of unresolved path
    refers to the actual file within this directory.  Filename extension and language variant is
    added automatically.

    For example a request to '/doc/wiking/user/navigation' is resolved as follows:
      * 'doc' must be mapped within application to the `Documentation' module.
      * 'wiking' is searched in `cfg.doc_dirs', where it translates for example to
        '/usr/local/share/wiking/doc/src'.
      * File '/usr/local/share/wiking/doc/src/user/navigation.<lang>.txt'. is searched,
        where <lang> may be one of the application defined languages.  Prefered language
        is determined through `Request.prefered_language()'.

    """
    
    def _document_base_dir(self, req):
        """Return the documentation base directory."""
        if req.unresolved_path:
            component = req.unresolved_path[0]
            del req.unresolved_path[0]
        else:
            raise Forbidden()
        try:
            basedir = cfg.doc_dirs[component]
        except KeyError:
            log(OPR, "Component '%s' not found in 'cfg.doc_dirs':" % component, cfg.doc_dirs)
            raise NotFound()
        if not os.path.exists(basedir):
            raise Exception("Documentation directory for '%s' does not exist. "
                            "Please check 'doc_dirs' configuration option." % component)
        return basedir

    def _document_path(self, req):
        return req.unresolved_path
        
    def _handle(self, req):
        # TODO: the documentation should be processed by LCG first into some
        # reasonable output format.  Now we just search the file in all the
        # source directories and format it.  No global navigation is used.
        if not req.unresolved_path:
            raise Forbidden()
        import codecs
        basename = os.path.join(self._document_base_dir(req), *self._document_path(req))
        variants = [lang for lang in self._application.languages()
                    if os.path.exists('.'.join((basename, lang, 'txt')))]
        if not variants:
            # HACK: Try fallback to English if no application language variants
            # are available.  In fact, the application should never return
            # content in any other language, than what is defined by
            # `Application.languages()', but default Wiking documentation is
            # often not translated to application languages and users get a
            # confusing error.  This should avoid the confusion, but a proper
            # solution would be to have all documentation files translated at
            # least to one application language.
            if os.path.exists('.'.join((basename, 'en', 'txt'))):
                variants = ['en']
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
            content = lcg.Container(content[0].content())
        else:
            title = ' :: '.join(req.unresolved_path)
        return Document(title, content, lang=lang, variants=variants)
        

class Stylesheets(Module, RequestHandler):
    """Serve installed stylesheets.

    The default implementation serves stylesheet files from the wiking resources directory.

    Map the module to a particular URI within your application to use it.

    """

    _MATCHER = re.compile (r"\$(\w[\w-]*)(?:\.(\w[\w-]*))?")

    def _stylesheet(self, path):
        for resource_dir in cfg.resource_path:
            filename = os.path.join(resource_dir, 'css', *path)
            if os.path.exists(filename):
                return "".join(file(filename).readlines())
        raise NotFound()

    def _theme(self, req):
        """Return the color theme to be used for stylesheet color substitution.

        Returns cfg.theme by default but may be overriden to select the current theme based on some
        application specific logic (eg. according to user's preferences, etc.).
        
        """
        return cfg.theme

    def _substitute(self, stylesheet, theme):
        def subst(match):
            name, key = match.groups()
            value = theme[name]
            if key:
                value = value[key]
            return value
        return self._MATCHER.sub(subst, stylesheet)

    def _handle(self, req):
        """Serve the stylesheet from a file."""
        if len(req.unresolved_path) >= 1:
            theme = self._theme(req)
            stylesheet = self._stylesheet(req.unresolved_path)
            return ('text/css', self._substitute(stylesheet, theme))
        elif not req.unresolved_path:
            raise Forbidden()
        else:
            raise NotFound()
        

class Resources(Module, RequestHandler):
    """Serve the resource files as provided by the LCG's 'ResourceProvider'.

    This module will automatically serve all resources found within the directories configured
    through the 'resource_path' option.  Use with caution, since this module will expose all files
    located within configured directories to the internet!  Note that the LCG's default resource
    directory (as configured within the LCG package) is always automatically added to the search
    path.

    Map the module to a particular URI within your application to use it.

    """

    def __init__(self, *args, **kwargs):
        super(Resources, self).__init__(*args, **kwargs)
        self._provider = lcg.ResourceProvider(dirs=cfg.resource_path)

    def _handle(self, req):
        """Serve the resource from a file."""
        if len(req.unresolved_path) > 1 and '..' not in req.unresolved_path:
            subdir = req.unresolved_path[0]
            filename = os.path.join(*req.unresolved_path[1:])
            resource = self._provider.resource(filename)
            if resource is not None and resource.SUBDIR == subdir:
                src_file = resource.src_file()
                if src_file:
                    import mimetypes
                    mime_type, encoding = mimetypes.guess_type(src_file)
                    return req.serve_file(src_file, mime_type or 'application/octet-stream')
        raise NotFound()


class SiteIcon(Module, RequestHandler):
    """Serve site icon according to the configuration option 'site_icon'.

    This module is mapped to '/favicon.ico' in the default 'Application'.

    """
    
    def _handle(self, req):
        filename = cfg.site_icon
        if filename:
            return req.serve_file(filename, 'image/vnd.microsoft.icon')
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
        item = find(self._application.menu(req), id)
        if item:
            if item.submenu():
                raise Redirect(req.uri_prefix() +'/'+ item.submenu()[0].id())
            else:
                raise Exception("Menu item '%s' has no childs." % id)
        else:
            raise Exception("Menu item for '%s' not found." % id)
            

class CookieAuthentication(object):
    """Implementation of cookie based authentication for Wiking Application.

    This class implements cookie based authentication, but is still neutral to authentication data
    source.  Any possible source of authentication data may be used by implementing the methods
    '_auth_user()' and '_auth_check_password()'.  See their documentation for more information.
    Moreover, the method '_auth_hook()' allows logging authentication attempts.

    This class may be used as a Mix-in class derived by the application which wishes to use it.

    """
    
    _LOGIN_COOKIE = 'wiking_login'
    _SESSION_COOKIE = 'wiking_session_key'
    _SECURE_AUTH_COOKIES = False

    def _auth_user(self, req, login):
        """Obtain authentication data and return a 'User' instance for given 'login'.

        This method may be used to retrieve authentication data from any source, such as database
        table, file, LDAP server etc.  This should return the user corresponding to given login
        name if it exists.  Further password checking is performed later by the
        '_auth_check_password()' method.  'None' may be returned if no user exists for given login
        name.

        """
        return None

    def _auth_check_password(self, user, password):
        """Check authentication password for given user.

        Arguments:
        
          user -- 'User' instance
          password -- supplied password as a string

        Return True if given password is the correct login password for given user.

        """
        return False

    def _auth_hook(self, req, login, user, initial, success):
        """Hook executed on each authentication attempt.

        Arguments:
        
          req -- current request object
          login -- login name supplied by the user
          user -- 'User' instance or None if '_auth_user()' didn't find a user matching given login
            name
          initial -- True if this is the initial login or False during an existing session.
          success -- True if the authentication was successful, False otherwise

        This hook is mainly designed to allow logging user acces and/or invalid login attempts.

        """ 
        pass
    
    def authenticate(self, req):
        try:
            session = self._module('Session')
        except MaintenanceModeError:
            return None
        # When HTTP authentication is used, req.credentials() returns the
        # credentials for every subsequent request (for cookie authentication
        # the credentials are sent just once on login form submission).  This
        # is quite unfortunate, since it results in new session initialization
        # for each request.  This should be solved if HTTP authentication is
        # used seriously.  Probably there should be two separate methods to
        # return login form credentials and HTTP authentication credentials.
        # HTTP authentication should probably not interfer with session at all
        # and should be implemented in a separate class.  The question is how
        # to combine the two methods nicely together.  It is important to
        # support login hooks for HTTP authentication too, otherwise the users
        # would be able to use HTTP authentication to make unnoticed logins.
        credentials = req.credentials()
        secure = self._SECURE_AUTH_COOKIES
        day = 24*3600
        if credentials:
            login, password = credentials
            if not login:
                raise AuthenticationError(_("Enter your login name, please!"))
            if not password:
                raise AuthenticationError(_("Enter your password, please!"))
            user = self._auth_user(req, login)
            if not user or not self._auth_check_password(user, password):
                self._auth_hook(req, login, user, initial=True, success=False)
                session.failure(req, user, login)
                raise AuthenticationError(_("Invalid login!"))
            assert isinstance(user, User)
            # Login succesfull
            self._auth_hook(req, login, user, initial=True, success=True)
            session_key = session.session_key()
            req.set_cookie(self._LOGIN_COOKIE, login, expires=730*day, secure=secure)
            req.set_cookie(self._SESSION_COOKIE, session_key, secure=secure)
            session.init(req, user, session_key)
        else:
            login, session_key = (req.cookie(self._LOGIN_COOKIE),
                                  req.cookie(self._SESSION_COOKIE))
            if login and session_key:
                user = self._auth_user(req, login)
                if user and session.check(req, user, session_key):
                    assert isinstance(user, User)
                    # Session cookie expiration is unset to prevent cookie persistency.
                    # Session expiration is implemented internally by the session module.
                    req.set_cookie(self._SESSION_COOKIE, session_key, secure=secure)
                    self._auth_hook(req, login, user, initial=False, success=True)
                else:
                    session_timed_out = True # This is not true after logout.
                    user = None
            else:
                user = None
        if req.param('command') == 'logout' and user:
            session.close(req, user, session_key)
            user = None
            req.set_cookie(self._SESSION_COOKIE, None, secure=secure)
        elif req.param('command') == 'login' and not user:
            raise AuthenticationRedirect()
        if user is not None:
            user.set_authentication_parameters(method='password', auto=False)
            password_expiration = user.password_expiration()
            if password_expiration is not None and req.uri() != self.password_change_uri(req):
                import datetime
                if password_expiration <= datetime.date.today():
                    raise PasswordExpirationError()
        return user

    
class Session(Module):
    """Session management module abstract interface.

    The 'Session' module is required by 'CookieAuthentication' module.  The application must
    implement the methods 'init()', 'check()' and 'close()' to store session information between
    requests.
    
    """

    def session_key(self, length=32):
        """Generate a new random session key and return it as a string.

        Arguments:
        
          length -- Size of session key in *bytes* (the length of the hex string representation is
            twice as much)

        This method may be used to generate a new key to be passed to the 'init()' method, but the
        caller may decide to generate the key himself.  In any case, the security of the
        authentication method depends on the randomness of the session key, so it should be done
        with caution.

        """
        return ''.join(['%02x' % ord(c) for c in os.urandom(length)])
        #except NotImplementedError:
        #    import random
        #    return hex(random.randint(0, pow(256, length)))[2:]
    
    def init(self, req, user, session_key):
        """Begin new session for given user ('User' instance) with given session key.

        The method is responsible for storing given session key in a persistent storage to allow
        later checking during upcoming requests.

        The caller is responsible for storing the session key within the user's browser as a cookie
        and passing it back to the 'check()' or 'close()' methods within upcoming requests.

        The method 'session_key()' may be used to generate a new session key to be passed as the
        'session_key' argument.

        """
        return None
        
    def check(self, req, user, session_key):
        """Return true if session_key is valid for an active session of given user."""
        return False

    def close(self, req, user, session_key):
        """Remove persistent session information and clean-up after user logged out."""
        pass
    
    def failure(self, req, user, login):
        """Store information about unsuccessful login attempt (optional)."""
        return None
        

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

        def _contents(self, generator):
            return (generator.label(self._SEARCH_FIELD_LABEL, id='input'), ' ',
                    generator.field(name='input', id='input', tabindex=0, size=20),
                    generator.br(),
                    generator.submit(self._SEARCH_BUTTON_LABEL, cls='submit'),)
        
        def export(self, exporter):
            generator = exporter.generator()
            contents = self._contents(generator)
            contents = contents + (generator.hidden(name='action', value='search'),)
            return generator.form(contents, method='POST', action=self._uri)

    class Result:
        def __init__ (self, uri, title, sample=None):
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
        return Document(self._SEARCH_TITLE, lcg.Container(content))

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
        return Document(self._RESULT_TITLE, content)
    
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
                except:
                    pass
        return module_names
    
    def _handle(self, req):
        module_names = self._reload_modules(req)
        content = lcg.coerce((lcg.p(_("The following modules were successfully reloaded:")),
                              lcg.p(", ".join(module_names)),))
        return Document(_("Reload"), lcg.coerce(content))
        

