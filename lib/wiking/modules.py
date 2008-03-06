# Copyright (C) 2005, 2006, 2007, 2008 Brailcom, o.p.s.
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

    @classmethod
    def name(cls):
        """Return module name as a string."""
        return cls.__name__

    @classmethod
    def title(cls):
        """Return human-friendly module name as a string or 'lcg.LocalizableText'."""
        return cls.__name__

    @classmethod
    def descr(cls):
        """Return brief module description as a string or 'lcg.LocalizableText'."""
        return doc(cls)

    def __init__(self, get_module, **kwargs):
        """Initialize the instance.

        Arguments:

          get_module -- a callable object which returns the module instance
            when called with a module name as an argument.

        """
        self._module = get_module
        #log(OPR, 'New module instance: %s[%x]' % (self.name(), lcg.positive_id(self)))
        super(Module, self).__init__(**kwargs)

    
class RequestHandler(object):
    """Mix-in class for modules capable of handling requests."""
    
    def __init__(self, *args, **kwargs):
        self._cached_uri = (None, None)
        self._application = self._module('Application')
        super(RequestHandler, self).__init__(*args, **kwargs)
    
    def _mapped_uri(self):
        # Retrive the current mapping uri for the module.  This method is used by _base_uri() and
        # may be overriden in derived classes.  The result may be cached for the duration of one
        # request.
        return self._application.module_uri(self.name())

    def _base_uri(self, req):
        """Return module's current URI as a string or None if not mapped."""
        # Since the identifiers may be used many times, they are cached at least for the duration
        # of one request.  We cannot cache them over requests, sice there is no way to invalidate
        # them if mapping changes (at least in the multiprocess server invironment).
        req_, uri = self._cached_uri
        if req is not req_:
            uri = self._mapped_uri()
            if uri is None:
                handlers = req.handlers()
                try:
                    module = handlers[handlers.index(self) - 1]
                except (IndexError, ValueError):
                    pass
                else:
                    uri = module._mapped_uri()
            if uri is not None:
                uri = req.uri_prefix() + uri
            self._cached_uri = (req, uri)
        return uri

    def _authorize(self, req, **kwargs):
        if not self._application.authorize(req, self, **kwargs):
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

    def _handle(self, req, action, **kwargs):
        """Perform action authorization and call the action method."""
        self._authorize(req, action=action, **kwargs)
        method = getattr(self, 'action_'+ action)
        return method(req, **kwargs)

    def handle(self, req):
        kwargs = self._action_args(req)
        if req.has_param('action'):
            action = req.param('action')
        else:
            action = self._default_action(req, **kwargs)
        return self._handle(req, action, **kwargs)


class DocumentHandler(Module, RequestHandler):
    _BASE_DIR = None
    
    def _document(self, req, basedir, path):
        if not os.path.exists(basedir):
            raise Exception("Directory %s does not exist" % basedir)
        import glob, codecs
        # TODO: the documentation should be processed by LCG first into some
        # reasonable output format.  Now we just search the file in all the
        # source directories and format it.  No global navigation is used.
        for subdir in ('', 'user', 'cms', 'admin', 'devel'):
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
        
    def _handle(self, req):
        return self._document(req, self._BASE_DIR, req.path)
        

class Documentation(DocumentHandler):
    """Serve the on-line documentation.

    This module is not bound to a data object.  It only serves the on-line documentation from files
    on the disk.

    """
    def _handle(self, req):
        path = req.path[1:]
        if path and path[0] == 'lcg':
            path = path[1:]
            basedir = lcg.config.doc_dir
        else:
            basedir = os.path.join(cfg.wiking_dir, 'doc', 'src')
        return self._document(req, basedir, path)


class Stylesheets(Module, RequestHandler):
    """Manages available stylesheets and serves them to the client.

    The default implementation serves stylesheet files from the wiking resources directory.  You
    will just need to map this module to serve certain uri, such as 'css'.

    """

    _MATCHER = re.compile (r"\$(\w[\w-]*)(?:\.(\w[\w-]*))?")

    def _stylesheet(self, name):
        filename = os.path.join(cfg.wiking_dir, 'resources', 'css', name)
        if os.path.exists(filename):
            return "".join(file(filename).readlines())
        else:
            raise NotFound()

    def _substitute(self, data):
        theme = cfg.theme
        def subst(match):
            name, key = match.groups()
            value = theme[name]
            if key:
                value = value[key]
            return value
        return self._MATCHER.sub(subst, data)

    def _handle(self, req):
        """Serve the stylesheet from a file."""
        return ('text/css', self._substitute(self._stylesheet(req.path[1])))

    
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
                return req.redirect(req.uri_prefix() +'/'+ item.submenu()[0].id())
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

        This method may be used to retieve authentication data from any source, such as database
        table, file, LDAP server etc.  This should return the user corresponding to given login
        name if it exists.  Further password checking is performed later by the
        '_auth_check_password()' method.  None may be returned if no user exists for given login
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
        except MaintananceModeError:
            return None
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
                raise AuthenticationError(_("Invalid login!"))
            assert isinstance(user, User)
            # Login succesfull
            self._auth_hook(req, login, user, initial=True, success=True)
            session_key = session.init(user)
            req.set_cookie(self._LOGIN_COOKIE, login, expires=730*day, secure=secure)
            req.set_cookie(self._SESSION_COOKIE, session_key, secure=secure)
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
        return user

    
class Session(Module):
    _SESSION_KEY_LENGTH = 32
    """Size of session key in *bytes* (the length of the string representation is double)."""

    def _new_session_key(self):
        return ''.join(['%02x' % ord(c) for c in os.urandom(self._SESSION_KEY_LENGTH)])
        #except NotImplementedError:
        #    import random
        #    return hex(random.randint(0, pow(256, self._SESSION_KEY_LENGTH)))[2:]
    
    def _expiration(self):
        return mx.DateTime.now().gmtime() + mx.DateTime.TimeDelta(hours=2)

    def _expired(self, time):
        return time <= mx.DateTime.now().gmtime()
    
    def init(self, user):
        return None
        
    def check(self, req, user, session_key):
	return False

    def close(self, req, user, session_key):
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
            result_item = lcg.Paragraph((link,))
        else:
            result_item = lcg.DefinitionList((lcg.Definition(link, lcg.coerce(sample)),))
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
        

