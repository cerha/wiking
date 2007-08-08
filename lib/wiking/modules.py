# Copyright (C) 2005, 2006, 2007 Brailcom, o.p.s.
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

"""Basic wiking module classes.

The classes defined here don't define Wiking API.  The API is defined in the module 'api'.  The
classes defined here, however, may be used to implement the API in an application.

"""

_ = lcg.TranslatableTextFactory('wiking')

class Module(object):
    """Abstract base class defining the basic Wiking module."""
    
    def name(cls):
        """Return the module name as a string."""
        return cls.__name__
    name = classmethod(name)

    def title(cls):
        """Return a human-friendly module name as an 'lcg.LocalizableText' instance."""
        return cls.__name__
    title = classmethod(title)

    def descr(cls):
        """Return brief module description as an 'lcg.LocalizableText' instance."""
        return doc(cls)
    descr = classmethod(descr)

    def __init__(self, get_module, resolver, **kwargs):
        """Initialize the instance.

        Arguments:

          get_module -- a callable object which returns the module instance
            when called with a module name as an argument.
          resolver -- Pytis 'Resolver' instance.

        """
        self._module = get_module
        self._resolver = resolver
        #log(OPR, 'New module instance: %s[%x]' % (self.name(), lcg.positive_id(self)))
        super(Module, self).__init__(**kwargs)

    def menu(self, req):
        return self._module('Mapping').menu(req)
        
    def panels(self, req, lang):
        return self._module('Panels').panels(req, lang)

    
class RequestHandler(object):
    """Mix-in class for modules capable of handling requests."""
    
    def handle(self, req):
        """Handle the request and return the result.

        The result may be either a 'Document' instance or a pair (MIME_TYPE,
        DATA).  The document instance will be exported into HTML, the MIME data
        will be served directly.

        """
        pass


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

    def _action(self, req, action, **kwargs):
        method = getattr(self, 'action_' + action)
        return method(req, **kwargs)

    def handle(self, req):
        kwargs = self._action_args(req)
        if req.params.has_key('action'):
            action = req.param('action')
        else:
            action = self._default_action(req, **kwargs)
        return self._action(req, action, **kwargs)


class DocumentHandler(Module, RequestHandler):
    _BASE_DIR = None
    
    def _document(self, req, basedir, path):
        if not os.path.exists(basedir):
            raise Exception("Directory %s does not exist" % basedir)
        import glob, codecs
        # TODO: the documentation should be processed by LCG first into some
        # reasonable output format.  Now we just search the file in all the
        # source directories and format it.  No global navigation is used.
        for subdir in ('', 'user', 'admin'):
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
        
    def handle(self, req):
        return self._document(req, self._BASE_DIR, req.path)
        

class Documentation(DocumentHandler):
    """Serve the on-line documentation.

    This module is not bound to a data object.  It only serves the on-line documentation from files
    on the disk.

    """
    def handle(self, req):
        path = req.path[1:]
        if path and path[0] == 'lcg':
            path = path[1:]
            basedir = lcg.config.doc_dir
        else:
            basedir = os.path.join(cfg.wiking_dir, 'doc', 'src')
        return self._document(req, basedir, req.path[1:])

    def menu(self, req):
        return ()

    def panels(self, req, lang):
        return []


class CookieAuthentication(Module):
    """Authentication class implementing cookie based authentication.

    This class implements cookie based authentication, but is still neutral to authentication data
    source.  Any possible source of authentication data may be used by implementing the methods
    '_user()' and '_check()'.  See their documentation for more information.

    """
    
    _LOGIN_COOKIE = 'wiking_login'
    _SESSION_COOKIE = 'wiking_session_key'

    def _user(self, login):
        """Obtain authentication data and return a 'User' instance for given 'login'.

        This method may be used to retieve authentication data from any source, such as database
        table, file, LDAP server etc.  This should return the user corresponding to given login
        name if it exists.  Further password checking is performed later by the '_check()' method.
        None may be returned if no user exists for given login name.

        """
        return None

    def _check(self, user, password):
        """Check authentication password for given user.

        Arguments:
          user -- 'User' instance
          password -- supplied password as a string

        Return True if given password is the correct login password for given user.

        """
        return False
    
    def authenticate(self, req):
        session = self._module('Session')
        credentials = req.credentials()
        day = 24*3600
        if credentials:
            login, password = credentials
            if not login:
                raise AuthenticationError(_("Enter your login name, please!"))
            if not password:
                raise AuthenticationError(_("Enter your password, please!"))
            user = self._user(login)
            if not user or not self._check(user, password):
                raise AuthenticationError(_("Invalid login!"))
            assert isinstance(user, User)
            # Login succesfull
            session_key = session.init(user)
            req.set_cookie(self._LOGIN_COOKIE, login, expires=730*day)
            req.set_cookie(self._SESSION_COOKIE, session_key, expires=2*day)
        else:
            login, key = (req.cookie(self._LOGIN_COOKIE), 
                          req.cookie(self._SESSION_COOKIE))
            if login and key:
                user = self._user(login)
                if user and session.check(user, key):
                    assert isinstance(user, User)
                    # Cookie expiration is 2 days, but session expiration is
                    # controled within the session module independently.
                    req.set_cookie(self._SESSION_COOKIE, key, expires=2*day)
                else:
                    # This is not true after logout
                    session_timed_out = True
                    user = None
            else:
                user = None
        if req.param('command') == 'logout' and user:
            session.close(user)
            user = None
            req.set_cookie(self._SESSION_COOKIE, None, expires=0)
        elif req.param('command') == 'login' and not user:
            raise AuthenticationError()
        return user

    
class Session(Module):
    _MAX_SESSION_KEY = 0xfffffffffffffffffffffffffffff

    def _new_session_key(self):
        return hex(random.randint(0, self._MAX_SESSION_KEY))
    
    def _expiration(self):
        return mx.DateTime.now().gmtime() + mx.DateTime.TimeDelta(hours=2)

    def _expired(self, time):
        return time <= mx.DateTime.now().gmtime()
    
    def init(self, user):
        return None
        
    def check(self, user, session_key):
	return False

    def close(self, user):
        pass
    

class Search(Module, ActionHandler):

    _SEARCH_TITLE = _("Searching")
    _RESULT_TITLE = _("Search results")
    _EMPTY_SEARCH_MESSAGE = _("Given search term doesn't contain any searchable term.")

    class SearchForm(lcg.Content):
        
        _SEARCH_FIELD_LABEL = _("Search words: ")
        _SEARCH_BUTTON_LABEL = _("Search")

        def __init__(self, req):
            lcg.Content.__init__(self)
            self._params = req.params
            self._uri = req.uri

        def _contents(self, generator):
            return (generator.label(self._SEARCH_FIELD_LABEL, id='input'),
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
        variants = self._module('Languages').languages()
        lang = req.prefered_language(variants)
        return Document(self._SEARCH_TITLE, lcg.Container(content), lang=lang)

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
        variants = self._module('Languages').languages()
        lang = req.prefered_language(variants)
        return Document(self._RESULT_TITLE, content, lang=lang)
    
    # Actions
    
    def _default_action(self, req, **kwargs):
        return 'show'

    def action_show(self, req, **kwargs):
        return self._search_form(req)
        
    def action_search(self, req, **kwargs):
        input = req.params.get('input', '')
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
    
    def handle(self, req):
        module_names = self._reload_modules(req)
        content = lcg.coerce((lcg.p(_("The following modules were successfully reloaded:")),
                              lcg.p(", ".join(module_names)),))
        return Document(_("Reload"), lcg.coerce(content))
        

